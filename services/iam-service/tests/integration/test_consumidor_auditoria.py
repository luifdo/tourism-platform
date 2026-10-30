"""Consumidor `iam.auditoria` contra un RabbitMQ real (C-04, C-18, C-31, C-38, C-40).

La base es el FakeUnitOfWork: el SQL se prueba en test_auditoria_eventos_pg.py. Cada prueba
usa su propia cola (nombre único) con esperas de reintento cortas, salvo la del worker.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import aio_pika
import pytest
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue
from prometheus_client import REGISTRY

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.registrar_evento_auditoria import RegistrarEventoAuditoria
from app.config import Settings
from app.infrastructure.messaging import manejador_auditoria
from app.infrastructure.messaging.consumidor_rabbitmq import ConsumidorRabbitMQ, Manejador
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.manejador_auditoria import CLAVES, ManejadorAuditoria
from app.infrastructure.messaging.topologia_rabbitmq import EXCHANGE_DLX, declarar_topologia
from app.worker import construir_consumidores
from tests.fakes import FakeUnitOfWork

pytestmark = pytest.mark.rabbitmq

EXCHANGE = "turismo.eventos"
ESPERAS = (0.2, 0.2, 0.2)


def sobre(payload: dict[str, Any] | None = None, **cambios: Any) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "auditoria.registrada",
        "version": 1,
        "occurred_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "producer": "catalog-service",
        "correlation_id": "corr-catalog-1",
        "payload": {"accion": "ZONA_CREADA", "resultado": "EXITO", "ip_origen": "181.49.10.7"}
        if payload is None
        else payload,
    } | cambios


class Bus:
    """Publica como un productor y escucha la DLQ con una cola exclusiva propia."""

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> "Bus":
        self._conexion = await aio_pika.connect_robust(self.url)
        canal = await self._conexion.channel()
        self._eventos = await declarar_topologia(canal, EXCHANGE)
        dlx = await canal.declare_exchange(EXCHANGE_DLX, aio_pika.ExchangeType.TOPIC, durable=True)
        self.dlq: AbstractQueue = await canal.declare_queue(exclusive=True)
        await self.dlq.bind(dlx, routing_key="#")
        self.canal = canal
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._conexion.close()

    async def publicar(self, cuerpo: dict[str, Any] | bytes) -> None:
        datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
        await self._eventos.publish(
            aio_pika.Message(datos, type="auditoria.registrada"),
            routing_key="auditoria.registrada",
        )

    async def de_la_dlq(self) -> AbstractIncomingMessage:
        for _ in range(100):
            mensaje = await self.dlq.get(fail=False)
            if mensaje is not None:
                await mensaje.ack()
                return mensaje
            await asyncio.sleep(0.1)
        raise AssertionError("No llegó nada a la DLQ")

    async def dlq_vacia(self) -> bool:
        return await self.dlq.get(fail=False) is None


@pytest.fixture
async def bus(rabbitmq_url: str) -> AsyncIterator[Bus]:
    async with Bus(rabbitmq_url) as b:
        yield b


@pytest.fixture
async def consumir(
    rabbitmq_url: str,
) -> AsyncIterator[Callable[[Manejador], Awaitable[str]]]:
    """Arranca un consumidor en una cola propia y devuelve su nombre (etiqueta de la métrica)."""
    consumidores: list[ConsumidorRabbitMQ] = []

    async def iniciar(manejar: Manejador) -> str:
        cola = f"prueba.{uuid.uuid4().hex[:8]}"
        consumidor = ConsumidorRabbitMQ(rabbitmq_url, EXCHANGE, cola, CLAVES, manejar, ESPERAS)
        await consumidor.iniciar()
        consumidores.append(consumidor)
        return cola

    yield iniciar
    for consumidor in consumidores:
        await consumidor.cerrar()


def contador(cola: str, resultado: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "iam_eventos_consumidos_total",
            {"cola": cola, "event_type": "auditoria.registrada", "resultado": resultado},
        )
        or 0.0
    )


async def esperar(condicion: Callable[[], bool], segundos: float = 10) -> None:
    for _ in range(int(segundos / 0.1)):
        if condicion():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("La condición no se cumplió a tiempo")


def manejador_real(uow: FakeUnitOfWork) -> ManejadorAuditoria:
    return ManejadorAuditoria(RegistrarEventoAuditoria(lambda: uow))


async def test_guarda_el_evento_y_el_duplicado_no(bus: Bus, consumir: Any) -> None:
    uow = FakeUnitOfWork()
    cola = await consumir(manejador_real(uow))
    evento = sobre()

    await bus.publicar(evento)
    await esperar(lambda: contador(cola, "aplicado") == 1)
    await bus.publicar(evento)  # el productor reentrega el mismo event_id
    await esperar(lambda: contador(cola, "duplicado") == 1)

    [guardado] = uow.auditoria.eventos.values()
    assert str(guardado.event_id) == evento["event_id"]
    assert guardado.ocurrido_en == datetime.fromisoformat(evento["occurred_at"])
    assert guardado.correlation_id == "corr-catalog-1"
    assert await bus.dlq_vacia()


async def test_ip_invalida_no_va_a_la_dlq(bus: Bus, consumir: Any) -> None:
    uow = FakeUnitOfWork()
    cola = await consumir(manejador_real(uow))

    await bus.publicar(sobre({"accion": "EXPORT", "resultado": "EXITO", "ip_origen": "x"}))
    await esperar(lambda: contador(cola, "aplicado") == 1)

    [guardado] = uow.auditoria.eventos.values()
    assert guardado.ip_origen is None
    assert guardado.detalles == {"ip_origen_invalida": "x"}
    assert await bus.dlq_vacia()


@pytest.mark.parametrize(
    "cuerpo",
    [
        sobre({"accion": "EXPORT", "resultado": "Exito"}),  # payload fuera del contrato
        sobre(version=2),
        b"no es json",
    ],
    ids=["payload", "version", "json"],
)
async def test_fuera_del_contrato_va_directo_a_la_dlq(
    bus: Bus, consumir: Any, cuerpo: dict[str, Any] | bytes
) -> None:
    uow = FakeUnitOfWork()
    cola = await consumir(manejador_real(uow))

    await bus.publicar(cuerpo)
    muerto = await bus.de_la_dlq()

    assert muerto.headers["x-cola"] == cola
    assert muerto.headers["x-intentos"] == 0
    assert str(muerto.headers["x-error"])
    # El contador sube después del ack: el mensaje puede llegar a la DLQ un instante antes.
    await esperar(lambda: contador(cola, "dlq") == 1)
    assert contador(cola, "reintento") == 0
    assert uow.auditoria.eventos == {}


async def test_un_fallo_pasajero_se_reintenta(bus: Bus, consumir: Any) -> None:
    uow = FakeUnitOfWork()
    real = manejador_real(uow)
    fallos = 2

    async def falla_dos_veces(recibido: SobreEvento) -> ResultadoConsumo:
        nonlocal fallos
        if fallos:
            fallos -= 1
            raise ConnectionRefusedError("PostgreSQL caído")
        return await real(recibido)

    cola = await consumir(falla_dos_veces)
    await bus.publicar(sobre())
    await esperar(lambda: contador(cola, "aplicado") == 1)

    assert contador(cola, "reintento") == 2
    assert len(uow.auditoria.eventos) == 1
    assert await bus.dlq_vacia()


async def test_tras_tres_reintentos_va_a_la_dlq_y_no_vuelve(bus: Bus, consumir: Any) -> None:
    llamadas = 0

    async def siempre_falla(_: SobreEvento) -> ResultadoConsumo:
        nonlocal llamadas
        llamadas += 1
        raise ConnectionRefusedError("PostgreSQL caído")

    cola = await consumir(siempre_falla)
    await bus.publicar(sobre())
    muerto = await bus.de_la_dlq()

    assert muerto.headers["x-intentos"] == 4
    assert "ConnectionRefusedError" in str(muerto.headers["x-error"])
    await esperar(lambda: contador(cola, "dlq") == 1)
    assert contador(cola, "reintento") == 3
    await asyncio.sleep(1)  # C-40: nada lo saca de la DLQ para volver a intentarlo
    assert llamadas == 4


async def test_el_worker_declara_iam_auditoria_durable(rabbitmq_url: str) -> None:
    settings = Settings(rabbitmq_url=rabbitmq_url)
    [consumidor] = construir_consumidores(settings, sesiones=None)  # type: ignore[arg-type]
    await consumidor.iniciar()
    try:
        conexion = await aio_pika.connect_robust(rabbitmq_url)
        async with conexion:
            canal = await conexion.channel()
            # passive: falla si la cola no existe. Volver a declararla con los mismos
            # argumentos que catalog espera (durable + DLX) falla si existe con otros.
            cola = await canal.declare_queue(manejador_auditoria.COLA, passive=True)
            assert cola.name == "iam.auditoria"
            await canal.declare_queue(
                "iam.auditoria", durable=True, arguments={"x-dead-letter-exchange": EXCHANGE_DLX}
            )
            for espera in ("1s", "5s", "25s"):
                await canal.declare_queue(f"iam.auditoria.reintento.{espera}", passive=True)
    finally:
        await consumidor.cerrar()
