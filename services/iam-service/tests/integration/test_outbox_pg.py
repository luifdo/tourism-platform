"""Outbox contra PostgreSQL (C-09): misma transacción que el cambio y lado del relay."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.dto.evento_pendiente import EventoPendiente
from app.application.use_cases.cambiar_estado_usuario import (
    CambiarEstadoCommand,
    CambiarEstadoUsuario,
)
from app.config import get_settings
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.value_objects.enums import Rol
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.models import BitacoraAuditoria, Outbox
from app.infrastructure.persistence.models import Usuario as UsuarioModel
from app.infrastructure.persistence.outbox_pendiente import SqlAlchemyOutboxPendiente
from app.infrastructure.persistence.outbox_repository import SqlAlchemyOutbox
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import FakeRevocacion

pytestmark = pytest.mark.db

Sesiones = async_sessionmaker[AsyncSession]


def cuenta(email: str, rol: Rol) -> Usuario:
    return Usuario(
        email=email,
        password_hash="$argon2id$fake",
        nombre_completo="Prueba Outbox",
        rol=rol,
        habeas_data_aceptado=True,
        habeas_data_aceptado_en=datetime.now(UTC),
    )


async def sembrar(session_factory: Sesiones, *cuentas: Usuario) -> list[Usuario]:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        guardadas = [await uow.usuarios.add(c) for c in cuentas]
        await uow.commit()
    return guardadas


def suspension(minutos: int = 0) -> PrestadorSuspendido:
    return PrestadorSuspendido(
        ocurrido_en=datetime(2026, 10, 30, 10, minutos, tzinfo=UTC),
        usuario_id=uuid.uuid4(),
        suspendido_por=uuid.uuid4(),
    )


async def agregar(session_factory: Sesiones, *eventos: PrestadorSuspendido) -> None:
    async with session_factory() as session:
        for evento in eventos:
            await SqlAlchemyOutbox(session).agregar(evento)
        await session.commit()


async def test_el_evento_se_confirma_con_el_cambio_y_la_bitacora(
    session_factory: Sesiones,
) -> None:
    admin, prestador = await sembrar(
        session_factory,
        cuenta("outbox.admin@example.com", Rol.ADMIN),
        cuenta("outbox.prestador@example.com", Rol.PRESTADOR),
    )
    assert admin.id is not None and prestador.id is not None

    cambiar = CambiarEstadoUsuario(
        SqlAlchemyUnitOfWork(session_factory), FakeRevocacion(), lambda: datetime.now(UTC)
    )
    await cambiar.execute(
        CambiarEstadoCommand(
            admin_id=admin.id, usuario_id=prestador.id, motivo="RNT", ip_origen=None, activo=False
        )
    )

    async with session_factory() as session:
        [fila] = (
            await session.scalars(
                select(Outbox).where(
                    Outbox.sobre["payload"]["usuario_id"].astext == str(prestador.id)
                )
            )
        ).all()
        activo = await session.scalar(
            select(UsuarioModel.activo).where(UsuarioModel.id == prestador.id)
        )
        accion = await session.scalar(
            select(BitacoraAuditoria.accion).where(BitacoraAuditoria.usuario_id == admin.id)
        )
    assert fila.event_type == "prestador.suspendido"
    assert fila.publicado_en is None
    assert activo is False
    assert accion == "USER_STATUS_CHANGE"


async def test_si_no_se_puede_revocar_no_queda_ni_el_cambio_ni_el_evento(
    session_factory: Sesiones,
) -> None:
    admin, prestador = await sembrar(
        session_factory,
        cuenta("outbox.admin2@example.com", Rol.ADMIN),
        cuenta("outbox.prestador2@example.com", Rol.PRESTADOR),
    )
    assert admin.id is not None and prestador.id is not None
    cambiar = CambiarEstadoUsuario(
        SqlAlchemyUnitOfWork(session_factory), FakeRevocacion(caida=True), lambda: datetime.now(UTC)
    )

    with pytest.raises(ServicioNoDisponibleError):
        await cambiar.execute(
            CambiarEstadoCommand(
                admin_id=admin.id,
                usuario_id=prestador.id,
                motivo=None,
                ip_origen=None,
                activo=False,
            )
        )

    async with session_factory() as session:
        eventos = (
            await session.scalars(
                select(Outbox).where(
                    Outbox.sobre["payload"]["usuario_id"].astext == str(prestador.id)
                )
            )
        ).all()
        activo = await session.scalar(
            select(UsuarioModel.activo).where(UsuarioModel.id == prestador.id)
        )
    assert eventos == []
    assert activo is True


async def test_el_lote_marca_lo_confirmado_y_corta_al_primer_fallo(
    session_factory: Sesiones,
) -> None:
    primero, segundo, tercero = suspension(1), suspension(2), suspension(3)
    await agregar(session_factory, primero, segundo, tercero)
    ahora = datetime.now(UTC)
    recibidos: list[EventoPendiente] = []

    async def publicar(evento: EventoPendiente) -> None:
        if len(recibidos) == 1:
            raise ConnectionError("RabbitMQ caído")
        recibidos.append(evento)

    relay = SqlAlchemyOutboxPendiente(session_factory)
    resultado = await relay.procesar_lote(10, publicar, ahora)

    assert resultado.publicados == ("prestador.suspendido",)
    assert resultado.fallo is True
    assert recibidos[0].sobre["payload"]["usuario_id"] == str(primero.usuario_id)
    async with session_factory() as session:
        filas = {
            f.sobre["payload"]["usuario_id"]: f
            for f in (await session.scalars(select(Outbox))).all()
        }
    assert filas[str(primero.usuario_id)].publicado_en == ahora
    assert (
        filas[str(segundo.usuario_id)].publicado_en,
        filas[str(segundo.usuario_id)].intentos,
    ) == (
        None,
        1,
    )
    assert filas[str(tercero.usuario_id)].intentos == 0  # el lote se cortó antes

    estado = await relay.estado()
    assert estado.pendientes >= 2
    assert estado.mas_antiguo is not None

    borrados = await relay.limpiar_publicados(ahora + timedelta(seconds=1))
    assert borrados >= 1
    async with session_factory() as session:
        assert await session.get(Outbox, recibidos[0].event_id) is None


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Engine propio con commits reales: el SKIP LOCKED necesita dos conexiones."""
    engine = build_engine(get_settings().database_url)
    try:
        async with asyncio.timeout(3):
            async with engine.connect():
                pass
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL no responde: {type(exc).__name__}")
    yield engine
    await engine.dispose()


async def test_dos_relays_no_toman_el_mismo_evento(engine: AsyncEngine) -> None:
    sesiones = build_session_factory(engine)
    evento = suspension(4)
    await agregar(sesiones, evento)
    try:
        async with sesiones() as bloqueante, bloqueante.begin():
            # Un relay tiene el evento tomado...
            await bloqueante.execute(
                select(Outbox)
                .where(Outbox.sobre["payload"]["usuario_id"].astext == str(evento.usuario_id))
                .with_for_update()
            )
            # ...y el otro lo salta en lugar de esperarlo o publicarlo dos veces.
            vistos: list[EventoPendiente] = []

            async def publicar(e: EventoPendiente) -> None:
                vistos.append(e)

            await asyncio.wait_for(
                SqlAlchemyOutboxPendiente(sesiones).procesar_lote(100, publicar, datetime.now(UTC)),
                timeout=3,
            )
            assert str(evento.usuario_id) not in {v.sobre["payload"]["usuario_id"] for v in vistos}
    finally:
        async with sesiones() as session, session.begin():
            await session.execute(
                delete(Outbox).where(
                    Outbox.sobre["payload"]["usuario_id"].astext == str(evento.usuario_id)
                )
            )
