"""Relay del outbox contra PostgreSQL y RabbitMQ reales: entrega, broker caído y dos relays."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import aio_pika
import pytest
from aio_pika.abc import AbstractQueue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.infrastructure.messaging.publicador_rabbitmq import PublicadorRabbitMQ
from app.infrastructure.messaging.topologia_rabbitmq import COLA_DLQ, declarar_topologia
from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.persistence.repositorios.outbox_pendiente import SqlOutboxPendiente
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

Sesiones = async_sessionmaker[AsyncSession]
EXCHANGE = "turismo.eventos"
AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


class RelojFijo:
    def ahora(self) -> datetime:
        return AHORA

    def hoy(self) -> date:
        return AHORA.date()


@pytest.fixture
async def cola(rabbitmq_url: str) -> AsyncIterator[AbstractQueue]:
    """Cola temporal enlazada a todos los eventos, como lo hará cada consumidor con los suyos."""
    conexion = await aio_pika.connect_robust(rabbitmq_url)
    canal = await conexion.channel()
    eventos = await declarar_topologia(canal, EXCHANGE)
    cola = await canal.declare_queue(exclusive=True)
    await cola.bind(eventos, routing_key="#")
    yield cola
    await conexion.close()


async def guardar_eventos(sesiones: Sesiones, cantidad: int, correlacion: str = "corr-1") -> None:
    fijar_correlation_id(correlacion)
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        for i in range(cantidad):
            await uow.outbox.agregar(
                AuditoriaRegistrada(
                    usuario_id=uuid4(),
                    accion="ZONA_CREADA",
                    detalles={"orden": i},
                    ocurrido_en=AHORA + timedelta(milliseconds=i),
                )
            )
        await uow.confirmar()


def relay(sesiones: Sesiones, url: str, lote: int = 100) -> PublicarEventosPendientes:
    publicador = PublicadorRabbitMQ(url, EXCHANGE, timeout_segundos=3)
    return PublicarEventosPendientes(SqlOutboxPendiente(sesiones), publicador, RelojFijo(), lote)


async def recibir(cola: AbstractQueue, cantidad: int) -> list[aio_pika.abc.AbstractIncomingMessage]:
    mensajes = []
    async with cola.iterator(timeout=5) as iterador:
        async for mensaje in iterador:
            await mensaje.ack()
            mensajes.append(mensaje)
            if len(mensajes) == cantidad:
                break
    return mensajes


async def filas_outbox(sesiones: Sesiones) -> list:
    async with sesiones() as session:
        return list(
            await session.execute(
                text("SELECT event_id, publicado_en, intentos FROM outbox ORDER BY creado_en")
            )
        )


async def test_publica_con_clave_propiedades_y_sobre(
    sesiones: Sesiones, rabbitmq_url: str, cola: AbstractQueue
) -> None:
    await guardar_eventos(sesiones, 2, correlacion="corr-zona")
    resultado = await relay(sesiones, rabbitmq_url).execute()
    assert resultado.publicados == ("auditoria.registrada", "auditoria.registrada")
    assert not resultado.fallo

    mensajes = await recibir(cola, 2)
    primero = mensajes[0]
    sobre = json.loads(primero.body)
    assert primero.routing_key == "auditoria.registrada"
    assert primero.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert (primero.type, primero.correlation_id, primero.app_id) == (
        "auditoria.registrada",
        "corr-zona",
        "catalog-service",
    )
    assert primero.message_id == sobre["event_id"]
    assert set(sobre) == {
        "event_id",
        "event_type",
        "version",
        "occurred_at",
        "producer",
        "correlation_id",
        "payload",
    }
    assert [json.loads(m.body)["payload"]["detalles"]["orden"] for m in mensajes] == [0, 1]

    filas = await filas_outbox(sesiones)
    assert all(f.publicado_en == AHORA and f.intentos == 1 for f in filas)
    # Una segunda vuelta no publica nada más.
    assert (await relay(sesiones, rabbitmq_url).execute()).publicados == ()


async def test_con_el_broker_caido_queda_pendiente_y_sale_al_volver(
    sesiones: Sesiones, rabbitmq_url: str, cola: AbstractQueue
) -> None:
    await guardar_eventos(sesiones, 1)
    caido = await relay(sesiones, "amqp://guest:guest@127.0.0.1:1/").execute()
    assert caido.fallo and caido.publicados == ()
    [fila] = await filas_outbox(sesiones)
    assert fila.publicado_en is None and fila.intentos == 1

    vuelto = await relay(sesiones, rabbitmq_url).execute()
    assert vuelto.publicados == ("auditoria.registrada",)
    assert len(await recibir(cola, 1)) == 1


async def test_dos_relays_a_la_vez_no_duplican(
    sesiones: Sesiones, rabbitmq_url: str, cola: AbstractQueue
) -> None:
    await guardar_eventos(sesiones, 30)
    a, b = relay(sesiones, rabbitmq_url, lote=5), relay(sesiones, rabbitmq_url, lote=5)

    async def vaciar(caso: PublicarEventosPendientes) -> int:
        total = 0
        while publicados := (await caso.execute()).publicados:
            total += len(publicados)
        return total

    totales = await asyncio.gather(vaciar(a), vaciar(b))
    assert sum(totales) == 30
    ids = [m.message_id for m in await recibir(cola, 30)]
    assert len(set(ids)) == 30


async def test_limpia_solo_los_publicados_viejos(sesiones: Sesiones, rabbitmq_url: str) -> None:
    await guardar_eventos(sesiones, 2)
    await relay(sesiones, rabbitmq_url, lote=1).execute()  # publica uno
    outbox = SqlOutboxPendiente(sesiones)
    assert await outbox.limpiar_publicados(AHORA) == 0  # publicado justo en AHORA: no es viejo
    assert await outbox.limpiar_publicados(AHORA + timedelta(days=8)) == 1
    estado = await outbox.estado()
    assert estado.pendientes == 1 and estado.mas_antiguo is not None


async def test_la_topologia_incluye_la_dlq(rabbitmq_url: str) -> None:
    conexion = await aio_pika.connect_robust(rabbitmq_url)
    canal = await conexion.channel()
    await declarar_topologia(canal, EXCHANGE)
    await declarar_topologia(canal, EXCHANGE)  # declararla otra vez no cambia nada
    dlq = await canal.declare_queue(COLA_DLQ, passive=True)
    assert dlq.name == COLA_DLQ
    await conexion.close()
