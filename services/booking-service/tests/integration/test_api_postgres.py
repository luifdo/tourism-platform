"""Paso 5.2e: la unidad de trabajo en Postgres y la API completa con MODO_PERSISTENCIA=postgres."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, select

from config import Configuracion
from domain.servicio import ServicioRef
from infrastructure.http import demo
from infrastructure.persistence.db import fabrica_sesiones
from infrastructure.persistence.postgres import UnidadDeTrabajoPostgres
from infrastructure.persistence.tablas import disponibilidad_cupo, servicio_ref, solicitud_reserva
from main import crear_app

SERVICIO = str(demo.SERVICIO_DEMO)
TURISTA = {"X-Usuario-Id": str(demo.USUARIO_TURISTA_DEMO), "X-Usuario-Rol": "Turista"}
PRESTADOR = {"X-Usuario-Id": str(demo.USUARIO_PRESTADOR_DEMO), "X-Usuario-Rol": "Prestador"}
BASE = "/api/bookings"


# ---------- Unidad de trabajo ----------

def un_servicio() -> ServicioRef:
    return ServicioRef(uuid4(), uuid4(), uuid4(), 20, Decimal("50000"), True, 1)


@pytest.fixture
def uow(motor):
    return lambda: UnidadDeTrabajoPostgres(fabrica_sesiones(motor))


async def _borrar(motor, servicio_id):
    async with motor.begin() as con:
        await con.execute(delete(servicio_ref).where(servicio_ref.c.servicio_id == servicio_id))


async def test_con_commit_queda_guardado(uow, motor):
    s = un_servicio()
    try:
        async with uow() as u:
            await u.servicios.guardar_si_mas_nuevo(s)
            await u.commit()
        async with uow() as u:
            assert await u.servicios.leer(s.servicio_id) == s
    finally:
        await _borrar(motor, s.servicio_id)


async def test_sin_commit_se_deshace(uow):
    s = un_servicio()
    async with uow() as u:
        await u.servicios.guardar_si_mas_nuevo(s)
    async with uow() as u:
        assert await u.servicios.leer(s.servicio_id) is None


async def test_si_el_caso_de_uso_falla_a_mitad_se_deshace_todo(uow):
    s = un_servicio()
    with pytest.raises(ZeroDivisionError):
        async with uow() as u:
            await u.servicios.guardar_si_mas_nuevo(s)
            1 / 0  # cualquier error antes del commit
    async with uow() as u:
        assert await u.servicios.leer(s.servicio_id) is None


async def test_la_conexion_vuelve_al_pool(uow, motor):
    for _ in range(3):
        async with uow() as u:
            await u.servicios.leer(uuid4())
    assert motor.pool.checkedout() == 0


# ---------- API completa contra Postgres (fixture `cliente` en conftest.py) ----------

async def test_health_con_la_base_arriba(cliente):
    assert (await cliente.get("/health")).json() == {"status": "ok", "checks": {"postgres": "up"}}


async def test_health_503_si_la_base_no_responde():
    config = Configuracion(
        modo_persistencia="postgres", database_url="postgresql+asyncpg://booking:booking@127.0.0.1:1/booking_db"
    )
    app = crear_app(config)  # ya no lanza NotImplementedError
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://booking") as c:
        r = await c.get("/health")
    await app.state.contenedor.extras["motor"].dispose()
    assert r.status_code == 503 and r.json() == {"status": "degraded", "checks": {"postgres": "down"}}


async def test_sin_rutas_de_demo_en_modo_postgres(cliente):
    assert (await cliente.post("/dev/tareas/expirar")).status_code == 404


async def test_ciclo_completo_queda_en_postgres(cliente, motor, outbox):
    r = await cliente.post(
        BASE, json={"servicio_id": SERVICIO, "fecha_reserva": "2026-11-10", "numero_personas": 3}, headers=TURISTA
    )
    assert r.status_code == 201
    reserva_id = r.json()["id"]

    panel = (await cliente.get(f"{BASE}/prestador/solicitudes", headers=PRESTADOR)).json()
    assert [x["id"] for x in panel["items"]] == [reserva_id]
    assert (await cliente.post(f"{BASE}/{reserva_id}/confirmar", headers=PRESTADOR)).json()["estado"] == "CONFIRMADA"

    dias = (await cliente.get(
        f"{BASE}/disponibilidad", params={"servicio_id": SERVICIO, "desde": "2026-11-10", "hasta": "2026-11-11"}
    )).json()["dias"]
    assert [d["cupos_disponibles"] for d in dias] == [7, 10]

    r = await cliente.post(f"{BASE}/{reserva_id}/cancelar", headers=TURISTA)
    assert r.json()["estado"] == "CANCELADA"
    historial = (await cliente.get(f"{BASE}/mis-reservas", headers=TURISTA)).json()
    assert historial["total"] == 1 and historial["items"][0]["estado"] == "CANCELADA"

    # Lo confirmado está de verdad en booking_db, no en memoria:
    async with motor.connect() as con:
        estado = (await con.execute(
            select(solicitud_reserva.c.estado).where(solicitud_reserva.c.servicio_id == demo.SERVICIO_DEMO)
        )).scalars().all()
        cupos = (await con.execute(
            select(disponibilidad_cupo.c.cupos_disponibles)
            .where(disponibilidad_cupo.c.servicio_id == demo.SERVICIO_DEMO, disponibilidad_cupo.c.fecha == date(2026, 11, 10))
        )).scalar_one()
    assert estado == ["CANCELADA"] and cupos == 10
    tipos = [s["event_type"] for s in await outbox()]
    assert {"reserva.solicitada", "reserva.confirmada", "reserva.cancelada", "disponibilidad.actualizada"} <= set(tipos)


async def test_un_error_de_negocio_no_deja_nada_a_medias(cliente, motor, outbox):
    r = await cliente.post(
        BASE, json={"servicio_id": SERVICIO, "fecha_reserva": "2026-11-10", "numero_personas": 11}, headers=TURISTA
    )
    assert r.status_code == 409 and r.json()["error"] == "CUPOS_INSUFICIENTES"
    async with motor.connect() as con:
        assert (await con.execute(
            select(solicitud_reserva.c.id).where(solicitud_reserva.c.servicio_id == demo.SERVICIO_DEMO)
        )).first() is None
    assert await outbox() == []  # sin commit no queda ningún evento


async def test_conflicto_de_version_del_calendario_trae_el_dia_de_postgres(cliente):
    """ESC-09 sobre booking_db: el 409 trae el día tal como quedó guardado (con su tarifa)."""
    url = f"{BASE}/prestador/calendario/{SERVICIO}/2026-11-12"
    r = await cliente.put(url, json={"cupos_totales": 8, "tarifa_dia": 95000}, headers={**PRESTADOR, "If-Match": '"1"'})
    assert r.status_code == 200
    r = await cliente.put(url, json={"cupos_totales": 12}, headers={**PRESTADOR, "If-Match": '"1"'})
    assert r.status_code == 409 and r.headers["ETag"] == '"2"'
    cuerpo = r.json()
    assert cuerpo["version_actual"] == 2
    assert (cuerpo["actual"]["cupos_totales"], cuerpo["actual"]["version"]) == (8, 2)
    assert float(cuerpo["actual"]["tarifa_dia"]) == 95000
