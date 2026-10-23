"""Paso 5.2f: concurrencia real contra Postgres, por HTTP (ESC-02 / RNF de cero sobreventa).

En memoria, la prueba equivalente solo pasaba gracias al candado global: aquí no hay candado
en Python. Lo único que evita la sobreventa es el `SELECT ... FOR UPDATE` de la fila del día.
Todas las peticiones salen a la vez; cada una toma su propia conexión del pool (10 + 5),
así que las que no alcanzan conexión hacen fila (hasta `db_pool_espera_s`).
"""

import asyncio
from collections import Counter
from datetime import date
from uuid import uuid4

from sqlalchemy import func, select

from infrastructure.http import demo
from infrastructure.persistence.tablas import disponibilidad_cupo, solicitud_reserva

BASE = "/api/bookings"
DIA = date(2026, 11, 10)  # la demo lo abre con 10 cupos
CUPOS = 10


def turista() -> dict[str, str]:
    return {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Turista"}


async def solicitar(cliente, headers, personas=1):
    return await cliente.post(
        BASE,
        json={"servicio_id": str(demo.SERVICIO_DEMO), "fecha_reserva": DIA.isoformat(), "numero_personas": personas},
        headers=headers,
    )


async def estado_en_la_base(motor) -> tuple[int, int, int]:
    """(cupos_disponibles del día, reservas activas, personas en reservas activas), leído de booking_db."""
    r = solicitud_reserva.c
    async with motor.connect() as con:
        disponibles = (await con.execute(
            select(disponibilidad_cupo.c.cupos_disponibles)
            .where(disponibilidad_cupo.c.servicio_id == demo.SERVICIO_DEMO, disponibilidad_cupo.c.fecha == DIA)
        )).scalar_one()
        activas, personas = (await con.execute(
            select(func.count(), func.coalesce(func.sum(r.numero_personas), 0))
            .where(r.servicio_id == demo.SERVICIO_DEMO, r.fecha_reserva == DIA, r.estado.in_(["SOLICITADA", "CONFIRMADA"]))
        )).one()
    return disponibles, activas, personas


async def test_50_turistas_por_10_cupos_no_hay_sobreventa(cliente, motor):
    respuestas = await asyncio.gather(*(solicitar(cliente, turista()) for _ in range(50)))

    codigos = Counter(r.status_code for r in respuestas)
    assert codigos == {201: CUPOS, 409: 50 - CUPOS}  # ni un 500 ni un timeout del pool
    assert {r.json()["error"] for r in respuestas if r.status_code == 409} == {"CUPOS_INSUFICIENTES"}
    assert await estado_en_la_base(motor) == (0, CUPOS, CUPOS)
    solicitadas = [s for s in cliente.contenedor.publicador.publicados if s["event_type"] == "reserva.solicitada"]
    assert len(solicitadas) == CUPOS  # un evento por reserva que de verdad se creó


async def test_grupos_de_distinto_tamano_nunca_pasan_el_total(cliente, motor):
    """Peticiones de 1 a 4 personas: lo aceptado puede no llenar el día, pero nunca lo pasa."""
    tamanos = [1, 2, 3, 4] * 8
    respuestas = await asyncio.gather(*(solicitar(cliente, turista(), p) for p in tamanos))

    aceptadas = sum(p for p, r in zip(tamanos, respuestas) if r.status_code == 201)
    assert {r.status_code for r in respuestas} <= {201, 409}
    disponibles, _, personas = await estado_en_la_base(motor)
    assert aceptadas == personas <= CUPOS
    assert disponibles == CUPOS - personas
    # Todo rechazo es porque de verdad no cabía: si sobraba sitio para ese grupo, no se habría rechazado.
    assert all(p > disponibles for p, r in zip(tamanos, respuestas) if r.status_code == 409)


async def test_cancelaciones_y_solicitudes_a_la_vez_cuadran(cliente, motor):
    """Día lleno con 10 reservas; luego, a la vez, sus 10 turistas cancelan y 20 nuevos piden cupo.
    Al final, los cupos de la base coinciden exactamente con las reservas activas."""
    primeros = [turista() for _ in range(CUPOS)]
    reservas = [await solicitar(cliente, h) for h in primeros]
    assert {r.status_code for r in reservas} == {201}

    cancelar = [
        cliente.post(f"{BASE}/{r.json()['id']}/cancelar", headers=h) for r, h in zip(reservas, primeros)
    ]
    nuevas = [solicitar(cliente, turista()) for _ in range(20)]
    respuestas = await asyncio.gather(*cancelar, *nuevas)

    cancelaciones, solicitudes = respuestas[:CUPOS], respuestas[CUPOS:]
    assert {r.status_code for r in cancelaciones} == {200}
    assert {r.status_code for r in solicitudes} <= {201, 409}
    # Cuántas entran depende del orden de llegada; lo que no puede fallar es que todo cuadre.
    aceptadas = sum(r.status_code == 201 for r in solicitudes)
    disponibles, activas, personas = await estado_en_la_base(motor)
    assert activas == personas == aceptadas <= CUPOS
    assert disponibles == CUPOS - personas
