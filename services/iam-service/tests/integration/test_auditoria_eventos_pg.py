"""`registrar_evento` y `correlation_id` contra PostgreSQL (C-04, C-05, C-38, C-39)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.persistence.models import BitacoraAuditoria
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.db

Sesiones = async_sessionmaker[AsyncSession]


def evento(**cambios: Any) -> EventoAuditoria:
    datos: dict[str, Any] = {
        "event_id": uuid.uuid4(),
        "servicio_origen": "catalog-service",
        "ocurrido_en": datetime.now(UTC) - timedelta(hours=1),
        "accion": "ZONA_CREADA",
        "resultado": ResultadoAuditoria.EXITO,
        "usuario_id": None,
        "ip_origen": "181.49.10.7",
        "detalles": {"zona_id": "z-1"},
        "correlation_id": "corr-catalog-1",
    }
    return EventoAuditoria(**(datos | cambios))


async def crear_usuario(sesiones: Sesiones) -> uuid.UUID:
    async with SqlAlchemyUnitOfWork(sesiones) as uow:
        creado = await uow.usuarios.add(
            Usuario(
                email=f"auditoria.{uuid.uuid4().hex[:8]}@example.com",
                password_hash="$argon2id$fake",
                nombre_completo="Prueba Auditoría",
                rol=Rol.ENTIDAD,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=datetime.now(UTC),
            )
        )
        await uow.commit()
    assert creado.id is not None
    return creado.id


async def registrar(sesiones: Sesiones, recibido: EventoAuditoria) -> bool:
    async with SqlAlchemyUnitOfWork(sesiones) as uow:
        insertado = await uow.auditoria.registrar_evento(recibido)
        await uow.commit()
    return insertado


async def filas(sesiones: Sesiones, event_id: uuid.UUID) -> list[BitacoraAuditoria]:
    async with sesiones() as session:
        consulta = select(BitacoraAuditoria).where(BitacoraAuditoria.event_id == event_id)
        return list((await session.scalars(consulta)).all())


async def test_guarda_el_evento_con_la_fecha_del_hecho(session_factory: Sesiones) -> None:
    usuario_id = await crear_usuario(session_factory)
    hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    recibido = evento(usuario_id=usuario_id, ocurrido_en=hace_una_hora)

    assert await registrar(session_factory, recibido) is True

    [fila] = await filas(session_factory, recibido.event_id)
    assert fila.fecha == hace_una_hora  # occurred_at, no el momento de la inserción (C-39)
    assert fila.usuario_id == usuario_id
    assert fila.accion == "ZONA_CREADA"
    assert fila.resultado is ResultadoAuditoria.EXITO
    assert fila.servicio_origen == "catalog-service"
    assert str(fila.ip_origen) == "181.49.10.7"
    assert fila.detalles == {"zona_id": "z-1"}
    assert fila.correlation_id == "corr-catalog-1"


async def test_el_mismo_event_id_deja_una_sola_fila(session_factory: Sesiones) -> None:
    recibido = evento()

    assert await registrar(session_factory, recibido) is True
    assert await registrar(session_factory, recibido) is False

    assert len(await filas(session_factory, recibido.event_id)) == 1


async def test_usuario_inexistente_queda_nulo_y_su_id_en_detalles(
    session_factory: Sesiones,
) -> None:
    desconocido = uuid.uuid4()
    recibido = evento(usuario_id=desconocido, resultado=ResultadoAuditoria.DENEGADO)

    assert await registrar(session_factory, recibido) is True

    [fila] = await filas(session_factory, recibido.event_id)
    assert fila.usuario_id is None
    assert fila.detalles == {"zona_id": "z-1", "usuario_id_no_registrado": str(desconocido)}
    assert fila.resultado is ResultadoAuditoria.DENEGADO


async def test_sin_usuario_ni_ip_ni_correlation_id(session_factory: Sesiones) -> None:
    recibido = evento(ip_origen=None, correlation_id=None, detalles={})

    await registrar(session_factory, recibido)

    [fila] = await filas(session_factory, recibido.event_id)
    assert (fila.usuario_id, fila.ip_origen, fila.correlation_id) == (None, None, None)
    assert fila.detalles == {}


async def test_las_filas_propias_toman_el_correlation_id_de_la_peticion(
    session_factory: Sesiones,
) -> None:
    fijar_correlation_id("corr-peticion-iam")

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.auditoria.registrar(
            accion="ACCESS_DENIED",
            resultado=ResultadoAuditoria.DENEGADO,
            usuario_id=None,
            ip_origen=None,
            detalles={"motivo": "sin_token"},
        )
        await uow.commit()

    async with session_factory() as session:
        fila = await session.scalar(
            select(BitacoraAuditoria).where(BitacoraAuditoria.correlation_id == "corr-peticion-iam")
        )
    assert fila is not None
    assert fila.event_id is None
    assert fila.servicio_origen == "iam-service"
