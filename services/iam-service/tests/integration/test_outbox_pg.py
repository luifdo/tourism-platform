"""Outbox contra PostgreSQL (C-09): misma transacción que el cambio y lado del relay."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.application.dto.evento_pendiente import EventoPendiente
from app.application.use_cases.cambiar_estado_usuario import (
    CambiarEstadoCommand,
    CambiarEstadoUsuario,
)
from app.config import get_settings
from app.domain.entities.usuario import Usuario
from app.domain.events.evento_dominio import EventoDominio
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.events.usuario_suprimido import UsuarioSuprimido
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


def supresion(minutos: int = 0) -> UsuarioSuprimido:
    return UsuarioSuprimido(
        ocurrido_en=datetime(2026, 10, 30, 10, minutos, tzinfo=UTC),
        usuario_id=uuid.uuid4(),
        rol=Rol.PRESTADOR,
    )


async def agregar(session_factory: Sesiones, *eventos: EventoDominio) -> None:
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


@pytest.mark.usefixtures("sin_pendientes_ajenos")
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
            # Un relay tiene los eventos tomados, también los que dejó pendientes el uso normal
            # de la base de desarrollo: esta prueba hace commits reales y no debe marcarlos...
            await bloqueante.execute(
                select(Outbox).where(Outbox.publicado_en.is_(None)).with_for_update()
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


# ---------- Retención (C-63) ----------

RETENIDOS = ["usuario.suprimido"]


def usuario_de(evento: EventoPendiente) -> str:
    return evento.sobre["payload"]["usuario_id"]


@pytest.mark.usefixtures("sin_pendientes_ajenos")
async def test_los_retenidos_no_ocupan_el_lote_aunque_sean_los_mas_antiguos(
    session_factory: Sesiones,
) -> None:
    retenido, detras = supresion(0), suspension(1)
    await agregar(session_factory, retenido, detras)
    recibidos: list[EventoPendiente] = []

    async def publicar(evento: EventoPendiente) -> None:
        recibidos.append(evento)

    outbox = SqlAlchemyOutboxPendiente(session_factory, RETENIDOS)
    # Lote de 1: si el retenido lo ocupara, el de detrás nunca saldría.
    resultado = await outbox.procesar_lote(1, publicar, datetime.now(UTC))
    otra_vuelta = await outbox.procesar_lote(10, publicar, datetime.now(UTC))

    assert resultado.publicados == ("prestador.suspendido",)
    assert otra_vuelta.publicados == ()
    assert [usuario_de(e) for e in recibidos] == [str(detras.usuario_id)]
    async with session_factory() as session:
        fila = await session.scalar(
            select(Outbox).where(
                Outbox.sobre["payload"]["usuario_id"].astext == str(retenido.usuario_id)
            )
        )
    assert fila is not None
    assert (fila.publicado_en, fila.intentos) == (None, 0)


@pytest.mark.usefixtures("sin_pendientes_ajenos")
async def test_estado_no_cuenta_los_retenidos(session_factory: Sesiones) -> None:
    await agregar(session_factory, supresion(0), suspension(5))

    con_retencion = await SqlAlchemyOutboxPendiente(session_factory, RETENIDOS).estado()
    sin_retencion = await SqlAlchemyOutboxPendiente(session_factory, []).estado()

    # La alerta de relay atascado (C-40) no debe dispararse por una supresión retenida.
    assert (con_retencion.pendientes, con_retencion.mas_antiguo) == (1, suspension(5).ocurrido_en)
    assert con_retencion.retenidos == {"usuario.suprimido": 1}
    assert (sin_retencion.pendientes, sin_retencion.mas_antiguo) == (2, supresion(0).ocurrido_en)
    assert sin_retencion.retenidos == {}


@pytest.mark.usefixtures("sin_pendientes_ajenos")
async def test_con_la_lista_vacia_salen_en_orden_de_creado_en(session_factory: Sesiones) -> None:
    primero, segundo, tercero = supresion(0), suspension(1), supresion(2)
    # Se agregan desordenados: el orden de salida es el de creado_en, no el de inserción.
    await agregar(session_factory, tercero, primero, segundo)
    recibidos: list[EventoPendiente] = []

    async def publicar(evento: EventoPendiente) -> None:
        recibidos.append(evento)

    resultado = await SqlAlchemyOutboxPendiente(session_factory, []).procesar_lote(
        10, publicar, datetime.now(UTC)
    )

    assert [usuario_de(e) for e in recibidos] == [
        str(primero.usuario_id),
        str(segundo.usuario_id),
        str(tercero.usuario_id),
    ]
    assert resultado.publicados == (
        "usuario.suprimido",
        "prestador.suspendido",
        "usuario.suprimido",
    )


async def test_la_busqueda_del_lote_sigue_usando_el_indice_parcial(
    connection: AsyncConnection,
) -> None:
    # Sin secuencial, el planificador muestra si el índice le sirve a esta consulta.
    await connection.execute(text("SET LOCAL enable_seqscan = off"))
    consulta = SqlAlchemyOutboxPendiente(None, RETENIDOS).consulta_lote(100)  # type: ignore[arg-type]
    sql = consulta.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})

    plan = "\n".join(fila[0] for fila in await connection.execute(text(f"EXPLAIN {sql}")))

    assert "ix_outbox_pendientes" in plan, plan
