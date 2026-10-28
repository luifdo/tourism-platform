"""Consumidor base contra RabbitMQ real, con un manejador de prueba.

Los manejadores de verdad (`review.elegibilidad`, `review.servicios`) llegan en el paso 5;
aquí se prueba lo común: aplicar, reintentar y mandar a la DLQ.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido
from tests.integration.conftest import Bus, Manejar

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
CLAVE = "reserva.finalizada"
Consumir = Callable[[tuple[str, ...], Manejar], Awaitable[str]]


def finalizada() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": CLAVE,
        "version": 1,
        "occurred_at": AHORA.isoformat(),
        "producer": "booking-service",
        "correlation_id": "corr-booking",
        "payload": {
            "reserva_id": str(uuid4()),
            "servicio_id": str(uuid4()),
            "turista_id": str(uuid4()),
            "prestador_id": str(uuid4()),
            "fecha_reserva": date(2026, 11, 14).isoformat(),
            "numero_personas": 2,
        },
    }


class Manejador:
    """Falla las primeras `fallos` veces (o siempre, con `error`) y anota lo que recibe."""

    def __init__(self, fallos: int = 0, error: Exception | None = None) -> None:
        self.fallos = fallos
        self.error = error
        self.llamadas = 0
        self.aplicados: list[SobreEvento] = []
        self.listo = asyncio.Event()

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        self.llamadas += 1
        if self.error is not None:
            raise self.error
        if self.llamadas <= self.fallos:
            raise RuntimeError("base de datos ocupada")
        self.aplicados.append(sobre)
        self.listo.set()
        return ResultadoConsumo.APLICADO


async def test_aplica_un_evento_valido(bus: Bus, consumir: Consumir) -> None:
    manejador = Manejador()
    await consumir((CLAVE,), manejador)
    evento = finalizada()

    await bus.publicar(evento)

    await asyncio.wait_for(manejador.listo.wait(), timeout=5)
    assert str(manejador.aplicados[0].event_id) == evento["event_id"]


async def test_un_fallo_pasajero_se_reintenta(bus: Bus, consumir: Consumir) -> None:
    manejador = Manejador(fallos=2)
    await consumir((CLAVE,), manejador)

    await bus.publicar(finalizada())

    await asyncio.wait_for(manejador.listo.wait(), timeout=10)
    assert manejador.llamadas == 3


async def test_tras_tres_reintentos_va_a_la_dlq(bus: Bus, consumir: Consumir) -> None:
    cola = await consumir((CLAVE,), Manejador(error=RuntimeError("siempre falla")))

    await bus.publicar(finalizada())

    mensaje = await bus.de_la_dlq()
    cabeceras = mensaje.headers or {}
    assert cabeceras["x-cola"] == cola
    assert cabeceras["x-intentos"] == 4
    assert "siempre falla" in str(cabeceras["x-error"])


async def test_un_evento_invalido_va_directo_a_la_dlq(bus: Bus, consumir: Consumir) -> None:
    manejador = Manejador(error=EventoInvalido("payload sin turista_id"))
    await consumir((CLAVE,), manejador)

    await bus.publicar(finalizada())

    mensaje = await bus.de_la_dlq()
    assert (mensaje.headers or {})["x-intentos"] == 0
    assert manejador.llamadas == 1


async def test_un_sobre_roto_va_a_la_dlq_sin_llegar_al_manejador(
    bus: Bus, consumir: Consumir
) -> None:
    manejador = Manejador()
    await consumir((CLAVE,), manejador)

    await bus.publicar({"event_type": CLAVE, "basura": True}, segun_contrato=False)

    await bus.de_la_dlq()
    assert manejador.llamadas == 0
