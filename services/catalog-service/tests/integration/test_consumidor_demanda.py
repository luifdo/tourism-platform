"""Consumidor `catalog.demanda` contra RabbitMQ y PostGIS reales: la demanda por día cuadra.

`bus` y `consumir` (conftest) dan a cada prueba su propia cola y esperas de reintento cortas.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.aplicar_evento_reserva import AplicarEventoReserva
from app.infrastructure.messaging.manejador_demanda import CLAVES, ManejadorDemanda
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
DIA = date(2026, 11, 5)
SERVICIO, PRESTADOR = uuid4(), uuid4()


def reserva(
    tipo: str,
    reserva_id: UUID,
    minutos: int,
    personas: int = 2,
    fecha: date = DIA,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": f"reserva.{tipo}",
        "version": 1,
        "occurred_at": (AHORA + timedelta(minutes=minutos)).isoformat(),
        "producer": "booking-service",
        "correlation_id": "corr-booking",
        "payload": {
            "reserva_id": str(reserva_id),
            "servicio_id": str(SERVICIO),
            "turista_id": str(uuid4()),
            "prestador_id": str(PRESTADOR),
            "fecha_reserva": fecha.isoformat(),
            "numero_personas": personas,
        }
        | extra,
    }


def manejador(sesiones: Sesiones) -> ManejadorDemanda:
    return ManejadorDemanda(AplicarEventoReserva(lambda: SqlUnidadDeTrabajo(sesiones)))


async def esperar(condicion: Callable[[], Awaitable[bool]], segundos: float = 10) -> None:
    for _ in range(int(segundos / 0.1)):
        if await condicion():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("La condición no se cumplió a tiempo")


async def demanda(sesiones: Sesiones, dia: date = DIA) -> int:
    """Personas en reservas activas (Solicitada + Confirmada) del servicio ese día."""
    async with sesiones() as session:
        return (
            await session.scalar(
                text(
                    "SELECT coalesce(sum(numero_personas), 0) FROM reserva_proyeccion"
                    " WHERE servicio_id = :s AND fecha_reserva = :d"
                    " AND estado IN ('SOLICITADA', 'CONFIRMADA')"
                ),
                {"s": SERVICIO, "d": dia},
            )
            or 0
        )


async def procesados(sesiones: Sesiones) -> int:
    async with sesiones() as session:
        return await session.scalar(text("SELECT count(*) FROM evento_procesado")) or 0


async def publicar_y_esperar(bus: Any, sesiones: Sesiones, *eventos: dict[str, Any]) -> None:
    antes = await procesados(sesiones)
    for evento in eventos:
        await bus.publicar(evento)

    async def listos() -> bool:
        return await procesados(sesiones) >= antes + len(eventos)

    await esperar(listos)


async def test_la_demanda_del_dia_sigue_el_ciclo_de_cada_reserva(
    sesiones: Sesiones, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    a, b, c = uuid4(), uuid4(), uuid4()
    await publicar_y_esperar(
        bus,
        sesiones,
        reserva("solicitada", a, 0, personas=2),
        reserva("solicitada", b, 0, personas=3),
        reserva("solicitada", c, 0, personas=4),
    )
    assert await demanda(sesiones) == 9

    await publicar_y_esperar(
        bus,
        sesiones,
        reserva("confirmada", a, 1, personas=2),  # sigue contando
        reserva("cancelada", b, 1, personas=3, cancelada_por="Prestador", motivo="Lluvia"),
        reserva("rechazada", c, 1, personas=4, motivo="Plazo de respuesta vencido"),
    )
    assert await demanda(sesiones) == 2

    await publicar_y_esperar(bus, sesiones, reserva("finalizada", a, 2))
    assert await demanda(sesiones) == 0  # ya pasó: no ocupa capacidad


async def test_modificada_mueve_la_demanda_de_dia(
    sesiones: Sesiones, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    r, otro_dia = uuid4(), DIA + timedelta(days=3)
    await publicar_y_esperar(bus, sesiones, reserva("solicitada", r, 0, personas=2))
    await publicar_y_esperar(
        bus,
        sesiones,
        reserva(
            "modificada",
            r,
            1,
            personas=5,
            fecha=otro_dia,
            fecha_anterior=DIA.isoformat(),
            numero_personas_anterior=2,
            expira_en=(AHORA + timedelta(hours=48)).isoformat(),
        ),
    )
    assert (await demanda(sesiones), await demanda(sesiones, otro_dia)) == (0, 5)


async def test_desordenado_y_duplicado_no_descuadran(
    sesiones: Sesiones, bus: Any, consumir: Any
) -> None:
    await consumir(CLAVES, manejador(sesiones))
    r = uuid4()
    cancelada = reserva("cancelada", r, 5, cancelada_por="Turista")
    # La cancelación llega primero; la solicitud, vieja, llega después y otra vez repetida.
    solicitada = reserva("solicitada", r, 0)
    await publicar_y_esperar(bus, sesiones, cancelada, solicitada)
    await bus.publicar(solicitada)
    await asyncio.sleep(1)
    assert await demanda(sesiones) == 0
    assert await procesados(sesiones) == 2


async def test_payload_invalido_va_a_la_dlq(sesiones: Sesiones, bus: Any, consumir: Any) -> None:
    await consumir(CLAVES, manejador(sesiones))
    # numero_personas >= 1: roto a propósito
    await bus.publicar(reserva("solicitada", uuid4(), 0, personas=0), segun_contrato=False)
    mensaje = await bus.de_la_dlq()
    assert mensaje.routing_key == "reserva.solicitada"
    assert await demanda(sesiones) == 0
