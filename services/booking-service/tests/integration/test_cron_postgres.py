"""Los CronJobs contra Postgres real: cambian el estado, liberan cupos y dejan los eventos en el outbox.

La reserva se crea por la API (fixture `cliente`, reloj fijo del 1 de noviembre a las 10:00) y la
tarea corre después con un reloj adelantado, como lo haría el CronJob días más tarde.
"""

from datetime import date, datetime

from sqlalchemy import select

import cron
from config import Configuracion
from domain.reglas import ZONA
from infrastructure.http import demo
from infrastructure.persistence.tablas import disponibilidad_cupo, solicitud_reserva
from infrastructure.reloj import RelojFijo

BASE = "/api/bookings"
SERVICIO = str(demo.SERVICIO_DEMO)
TURISTA = {"X-Usuario-Id": str(demo.USUARIO_TURISTA_DEMO), "X-Usuario-Rol": "Turista"}
PRESTADOR = {"X-Usuario-Id": str(demo.USUARIO_PRESTADOR_DEMO), "X-Usuario-Rol": "Prestador"}
FECHA = date(2026, 11, 10)


def _config(base_migrada: str) -> Configuracion:
    return Configuracion(modo_persistencia="postgres", database_url=base_migrada, datos_demo=False)


async def _solicitar(cliente) -> str:
    r = await cliente.post(
        BASE, json={"servicio_id": SERVICIO, "fecha_reserva": FECHA.isoformat(), "numero_personas": 3}, headers=TURISTA
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _estado_y_cupos(motor) -> tuple[str, int]:
    async with motor.connect() as con:
        estado = (await con.execute(
            select(solicitud_reserva.c.estado).where(solicitud_reserva.c.servicio_id == demo.SERVICIO_DEMO)
        )).scalar_one()
        cupos = (await con.execute(
            select(disponibilidad_cupo.c.cupos_disponibles)
            .where(disponibilidad_cupo.c.servicio_id == demo.SERVICIO_DEMO, disponibilidad_cupo.c.fecha == FECHA)
        )).scalar_one()
    return estado, cupos


async def test_expirar_solicitudes_rechaza_las_vencidas_y_libera_cupos(cliente, motor, outbox, base_migrada):
    await _solicitar(cliente)  # expira_en = 3 de noviembre, 10:00
    config = _config(base_migrada)

    antes_de_vencer = RelojFijo(datetime(2026, 11, 3, 9, 59, tzinfo=ZONA))
    assert await cron.ejecutar("expirar-solicitudes", config, antes_de_vencer) == 0

    vencida = RelojFijo(datetime(2026, 11, 3, 10, 15, tzinfo=ZONA))
    assert await cron.ejecutar("expirar-solicitudes", config, vencida) == 1
    assert await _estado_y_cupos(motor) == ("RECHAZADA", 10)

    sobres = await outbox()
    rechazo = next(s for s in sobres if s["event_type"] == "reserva.rechazada")
    assert rechazo["payload"]["motivo"] == "Plazo de respuesta vencido"
    assert "disponibilidad.actualizada" in [s["event_type"] for s in sobres]

    # Repetir la tarea no hace nada más (Guía §6.2: las transiciones son idempotentes).
    assert await cron.ejecutar("expirar-solicitudes", config, vencida) == 0


async def test_finalizar_reservas_cierra_las_confirmadas_de_dias_pasados(cliente, motor, outbox, base_migrada):
    reserva_id = await _solicitar(cliente)
    assert (await cliente.post(f"{BASE}/{reserva_id}/confirmar", headers=PRESTADOR)).status_code == 200
    config = _config(base_migrada)

    el_mismo_dia = RelojFijo(datetime(2026, 11, 10, 23, 0, tzinfo=ZONA))
    assert await cron.ejecutar("finalizar-reservas", config, el_mismo_dia) == 0

    al_dia_siguiente = RelojFijo(datetime(2026, 11, 11, 0, 15, tzinfo=ZONA))
    assert await cron.ejecutar("finalizar-reservas", config, al_dia_siguiente) == 1
    assert await _estado_y_cupos(motor) == ("FINALIZADA", 7)  # finalizar no libera cupos
    # Habilita la reseña en review-service; va junto con su auditoria.registrada (Guía §9).
    assert "reserva.finalizada" in [s["event_type"] for s in await outbox()]


def test_main_sale_con_0_contra_postgres(base_migrada):
    """Lo que ejecuta el contenedor del CronJob: `python -m cron <tarea>`."""
    assert cron.main(["finalizar-reservas"], _config(base_migrada)) == 0
