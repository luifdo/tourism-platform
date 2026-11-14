"""Relay del outbox contra PostgreSQL y RabbitMQ reales."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.entities.resena import Resena
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.infrastructure.messaging.publicador_rabbitmq import PublicadorRabbitMQ
from app.infrastructure.persistence.repositorios.outbox_pendiente import SqlOutboxPendiente
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.infrastructure.reloj import RelojSistema
from tests.integration.conftest import EXCHANGE, Bus, recibir

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
Sesiones = async_sessionmaker[AsyncSession]


async def resena_escrita(uow: Callable[[], SqlUnidadDeTrabajo]) -> Resena:
    turista, servicio = uuid4(), uuid4()
    elegible = ElegibilidadResena(
        turista_id=turista, servicio_id=servicio, ultima_visita=date(2026, 11, 14)
    )
    resena, evento = Resena.escribir(turista, servicio, elegible, ContenidoResena(5), AHORA)
    async with uow() as u:
        await u.resenas.guardar(resena)
        await u.outbox.agregar(evento)
        await u.confirmar()
    return resena


def relay(url: str, sesiones: Sesiones) -> PublicarEventosPendientes:
    return PublicarEventosPendientes(
        SqlOutboxPendiente(sesiones),
        PublicadorRabbitMQ(url, EXCHANGE, timeout_segundos=2),
        RelojSistema(),
        lote=100,
    )


async def test_publica_lo_pendiente_y_lo_marca(
    bus: Bus,
    rabbitmq_url: str,
    sesiones: Sesiones,
    uow: Callable[[], SqlUnidadDeTrabajo],
    engine: AsyncEngine,
) -> None:
    cola = await bus.escuchar("resena.publicada")
    resena = await resena_escrita(uow)

    resultado = await relay(rabbitmq_url, sesiones).execute()

    assert resultado.publicados == ("resena.publicada",) and not resultado.fallo
    mensaje = await recibir(cola, "No llegó resena.publicada")
    sobre = json.loads(mensaje.body)
    assert sobre["producer"] == "review-service"
    assert sobre["payload"]["resena_id"] == str(resena.id)
    assert mensaje.type == "resena.publicada"
    async with engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT count(*) FROM outbox WHERE publicado_en IS NULL")) == 0
        )


async def test_con_rabbitmq_caido_el_evento_sigue_pendiente(
    sesiones: Sesiones, uow: Callable[[], SqlUnidadDeTrabajo], engine: AsyncEngine
) -> None:
    await resena_escrita(uow)

    resultado = await relay("amqp://guest:guest@127.0.0.1:1/", sesiones).execute()

    assert resultado.fallo and resultado.publicados == ()
    async with engine.connect() as conn:
        pendientes, intentos = (
            await conn.execute(
                text("SELECT count(*), max(intentos) FROM outbox WHERE publicado_en IS NULL")
            )
        ).one()
    assert (pendientes, intentos) == (1, 1)


async def test_limpia_solo_lo_publicado_viejo(
    sesiones: Sesiones, uow: Callable[[], SqlUnidadDeTrabajo], engine: AsyncEngine
) -> None:
    await resena_escrita(uow)  # pendiente: nunca se borra
    await resena_escrita(uow)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE outbox SET publicado_en = now() - interval '8 days'"
                " WHERE event_id = (SELECT event_id FROM outbox LIMIT 1)"
            )
        )

    borrados = await SqlOutboxPendiente(sesiones).limpiar_publicados(
        datetime.now(UTC) - timedelta(days=7)
    )

    assert borrados == 1
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM outbox")) == 1
