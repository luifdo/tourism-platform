"""Relay del outbox contra RabbitMQ real (C-09, C-17, C-31).

El broker es el efímero de testcontainers (`rabbitmq_url`); la base, la de desarrollo con la
transacción que se deshace al terminar (`session_factory`).
"""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import aio_pika
import pytest
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.infrastructure.messaging.publicador_rabbitmq import PublicadorRabbitMQ
from app.infrastructure.persistence.models import Outbox
from app.infrastructure.persistence.outbox_pendiente import SqlAlchemyOutboxPendiente
from app.infrastructure.persistence.outbox_repository import SqlAlchemyOutbox
from app.worker import construir_relay

pytestmark = [pytest.mark.rabbitmq, pytest.mark.db]

EXCHANGE = "turismo.eventos"


@pytest.fixture
async def cola_prestadores(rabbitmq_url: str) -> AsyncIterator[AbstractQueue]:
    """Cola temporal con la misma clave que `catalog.prestadores`."""
    conexion = await aio_pika.connect_robust(rabbitmq_url)
    canal = await conexion.channel()
    exchange = await canal.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
    cola = await canal.declare_queue(f"prueba.prestadores.{uuid.uuid4().hex[:8]}", exclusive=True)
    await cola.bind(exchange, routing_key="prestador.suspendido")
    yield cola
    await conexion.close()


async def recibir(cola: AbstractQueue) -> AbstractIncomingMessage:
    async with cola.iterator(timeout=10) as mensajes:
        async for mensaje in mensajes:
            await mensaje.ack()
            return mensaje
    raise AssertionError("No llegó ningún mensaje")


async def test_el_relay_publica_y_marca_el_evento(
    rabbitmq_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    cola_prestadores: AbstractQueue,
) -> None:
    evento = PrestadorSuspendido(
        ocurrido_en=datetime.now(UTC), usuario_id=uuid.uuid4(), suspendido_por=uuid.uuid4()
    )
    async with session_factory() as session:
        await SqlAlchemyOutbox(session).agregar(evento)
        await session.commit()
    publicador = PublicadorRabbitMQ(rabbitmq_url, EXCHANGE, timeout_segundos=5)
    relay = construir_relay(
        Settings(rabbitmq_url=rabbitmq_url, outbox_lote=100),
        SqlAlchemyOutboxPendiente(session_factory),
        publicador,
    )
    try:
        await relay.una_vuelta(1.0)
        mensaje = await recibir(cola_prestadores)
    finally:
        await publicador.cerrar()

    sobre = json.loads(mensaje.body)
    assert sobre["payload"]["usuario_id"] == str(evento.usuario_id)
    assert (mensaje.routing_key, mensaje.type, mensaje.app_id) == (
        "prestador.suspendido",
        "prestador.suspendido",
        "iam-service",
    )
    assert mensaje.message_id == sobre["event_id"]
    assert mensaje.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    async with session_factory() as session:
        fila = await session.scalar(
            select(Outbox).where(Outbox.event_id == uuid.UUID(sobre["event_id"]))
        )
    assert fila is not None and fila.publicado_en is not None


async def test_sin_broker_el_evento_queda_pendiente(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    evento = PrestadorSuspendido(
        ocurrido_en=datetime.now(UTC), usuario_id=uuid.uuid4(), suspendido_por=uuid.uuid4()
    )
    async with session_factory() as session:
        await SqlAlchemyOutbox(session).agregar(evento)
        await session.commit()
    # Puerto cerrado: el envío falla y el relay reintenta más tarde con espera creciente.
    publicador = PublicadorRabbitMQ("amqp://guest:guest@127.0.0.1:1/", EXCHANGE, 1)
    relay = construir_relay(Settings(), SqlAlchemyOutboxPendiente(session_factory), publicador)

    espera = await relay.una_vuelta(1.0)

    assert espera == 2.0
    async with session_factory() as session:
        fila = await session.scalar(
            select(Outbox).where(
                Outbox.sobre["payload"]["usuario_id"].astext == str(evento.usuario_id)
            )
        )
    assert fila is not None
    assert (fila.publicado_en, fila.intentos) == (None, 1)
