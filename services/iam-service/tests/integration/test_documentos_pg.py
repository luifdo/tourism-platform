"""Documentos de verificación contra PostgreSQL (C-02, C-07, C-30, UC28)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.aprobar_prestador import AprobarPrestador, AprobarPrestadorCommand
from app.application.use_cases.subir_documento import SubirDocumento, SubirDocumentoCommand
from app.domain.entities.documento_verificacion import DocumentoVerificacion, EstadoVerificacion
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import EstadoDocumento, Rol, TipoDocumento
from app.domain.value_objects.filtro_prestadores import FiltroPrestadores
from app.infrastructure.persistence.models import BitacoraAuditoria, Outbox
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import FakeAlmacenDocumentos
from tests.unit.test_documentos_dominio import PDF, PNG

pytestmark = pytest.mark.db

Sesiones = async_sessionmaker[AsyncSession]


def ahora() -> datetime:
    return datetime.now(UTC)


async def sembrar(session_factory: Sesiones, rol: Rol = Rol.PRESTADOR) -> Usuario:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        u = await uow.usuarios.add(
            Usuario(
                email=f"doc.{uuid.uuid4().hex[:8]}@example.com",
                password_hash="$argon2id$fake",
                nombre_completo="Prestador Documentos",
                rol=rol,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=ahora(),
            )
        )
        await uow.commit()
    return u


def documento(u: Usuario, tipo: TipoDocumento, estado=EstadoDocumento.PENDIENTE):  # type: ignore[no-untyped-def]
    return DocumentoVerificacion(
        usuario_id=u.id,  # type: ignore[arg-type]
        tipo_documento=tipo,
        objeto_s3=f"{u.id}/{tipo.value}/{uuid.uuid4()}.pdf",
        tipo_contenido="application/pdf",
        tamano_bytes=10,
        estado=estado,
    )


async def test_la_base_impide_dos_vigentes_del_mismo_tipo(session_factory: Sesiones) -> None:
    u = await sembrar(session_factory)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.documentos.agregar(documento(u, TipoDocumento.RNT))
        await uow.documentos.agregar(documento(u, TipoDocumento.RUT))  # otro tipo: sí
        await uow.commit()

    with pytest.raises(IntegrityError, match="uq_documento_verificacion_vigente"):
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.documentos.agregar(documento(u, TipoDocumento.RNT))


async def test_retirar_marcar_e_historial(session_factory: Sesiones) -> None:
    u = await sembrar(session_factory)
    admin = await sembrar(session_factory, Rol.ADMIN)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        viejo = await uow.documentos.agregar(documento(u, TipoDocumento.RNT))
        await uow.documentos.retirar_vigente(u.id, TipoDocumento.RNT)  # type: ignore[arg-type]
        nuevo = await uow.documentos.agregar(documento(u, TipoDocumento.RNT))
        revisado = await uow.documentos.marcar_revisado(
            nuevo.id,  # type: ignore[arg-type]
            EstadoDocumento.RECHAZADO,
            admin.id,  # type: ignore[arg-type]
            ahora(),
            "Ilegible",
        )
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        vigentes = await uow.documentos.vigentes(u.id)  # type: ignore[arg-type]
        historial = await uow.documentos.historial(u.id)  # type: ignore[arg-type]
        leido = await uow.documentos.find_by_id(nuevo.id)  # type: ignore[arg-type]

    assert [d.id for d in vigentes] == [nuevo.id]
    assert {d.id: d.vigente for d in historial} == {nuevo.id: True, viejo.id: False}
    assert leido == revisado
    assert (leido.estado, leido.motivo_rechazo, leido.revisado_por) == (  # type: ignore[union-attr]
        EstadoDocumento.RECHAZADO,
        "Ilegible",
        admin.id,
    )


async def test_cola_de_revision_por_estado(session_factory: Sesiones) -> None:
    sin_docs = await sembrar(session_factory)
    pendiente = await sembrar(session_factory)
    aprobado = await sembrar(session_factory)
    rechazado = await sembrar(session_factory)
    turista = await sembrar(session_factory, Rol.TURISTA)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        for u, estados in (
            (pendiente, (EstadoDocumento.PENDIENTE, EstadoDocumento.APROBADO)),
            (aprobado, (EstadoDocumento.APROBADO, EstadoDocumento.APROBADO)),
            (rechazado, (EstadoDocumento.PENDIENTE, EstadoDocumento.RECHAZADO)),
        ):
            for tipo, estado in zip((TipoDocumento.RNT, TipoDocumento.RUT), estados, strict=True):
                await uow.documentos.agregar(documento(u, tipo, estado))
        await uow.commit()

    async def ids(estado: EstadoVerificacion) -> set[uuid.UUID]:
        # La base de desarrollo tiene otros prestadores: se pide todo y se miran los propios.
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            pagina = await uow.documentos.listar_prestadores(
                FiltroPrestadores(estado=estado, tamano=100)
            )
        assert pagina.total >= len(pagina.items)
        return {p.usuario_id for p in pagina.items}

    propios = {sin_docs.id, pendiente.id, aprobado.id, rechazado.id, turista.id}
    assert (await ids(EstadoVerificacion.INCOMPLETO)) & propios == {sin_docs.id}
    assert (await ids(EstadoVerificacion.PENDIENTE)) & propios == {pendiente.id}
    assert (await ids(EstadoVerificacion.APROBADO)) & propios == {aprobado.id}
    assert (await ids(EstadoVerificacion.RECHAZADO)) & propios == {rechazado.id}

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        todos = await uow.documentos.listar_prestadores(FiltroPrestadores(tamano=100))
    resumen = {p.usuario_id: p for p in todos.items}
    assert turista.id not in resumen  # solo cuentas con rol Prestador
    if aprobado.id in resumen:  # puede caer en otra página si la base tiene muchos
        assert len(resumen[aprobado.id].vigentes) == 2


async def test_carga_y_aprobacion_de_punta_a_punta(session_factory: Sesiones) -> None:
    u = await sembrar(session_factory)
    admin = await sembrar(session_factory, Rol.ADMIN)
    almacen = FakeAlmacenDocumentos()
    subir = SubirDocumento(SqlAlchemyUnitOfWork(session_factory), almacen, ahora)
    for tipo, contenido, razon in (
        (TipoDocumento.RNT, PDF, None),
        (TipoDocumento.RUT, PNG, "Hostal Tayrona SAS"),
    ):
        await subir.execute(
            SubirDocumentoCommand(
                usuario_id=u.id,  # type: ignore[arg-type]
                tipo=tipo,
                contenido=contenido,
                razon_social=razon,
                ip_origen="190.24.10.5",
            )
        )

    resultado = await AprobarPrestador(SqlAlchemyUnitOfWork(session_factory), ahora).execute(
        AprobarPrestadorCommand(admin_id=admin.id, usuario_id=u.id, ip_origen=None)  # type: ignore[arg-type]
    )

    assert resultado.estado is EstadoVerificacion.APROBADO
    assert resultado.razon_social == "Hostal Tayrona SAS"
    async with session_factory() as session:
        acciones = (
            await session.scalars(
                select(BitacoraAuditoria.accion).where(
                    BitacoraAuditoria.usuario_id.in_([u.id, admin.id])
                )
            )
        ).all()
        [evento] = (
            await session.scalars(
                select(Outbox).where(Outbox.sobre["payload"]["usuario_id"].astext == str(u.id))
            )
        ).all()
    # Sin orden: dentro de la transacción de la prueba, now() es el mismo para todas las filas.
    assert sorted(acciones) == ["DOCUMENT_UPLOAD", "DOCUMENT_UPLOAD", "PROVIDER_APPROVED"]
    assert evento.event_type == "prestador.aprobado"
    assert evento.sobre["payload"]["razon_social"] == "Hostal Tayrona SAS"
