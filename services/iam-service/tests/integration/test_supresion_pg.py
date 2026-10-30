"""Supresión y version del perfil contra PostgreSQL (C-27, C-49): restricciones reales."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.editar_perfil import EditarPerfil, EditarPerfilCommand
from app.application.use_cases.registrar_usuario import RegistrarUsuario, RegistrarUsuarioCommand
from app.application.use_cases.suprimir_datos import SuprimirDatos, SuprimirDatosCommand
from app.domain.entities.documento_verificacion import DocumentoVerificacion
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import CredencialesInvalidasError, VersionConflictoError
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import EstadoDocumento, Idioma, Rol, TipoDocumento
from app.domain.value_objects.filtro_prestadores import FiltroPrestadores
from app.infrastructure.persistence.models import BitacoraAuditoria, Outbox
from app.infrastructure.persistence.models import Usuario as UsuarioModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import FakeAlmacenDocumentos, FakePasswordHasher, FakeRevocacion

pytestmark = pytest.mark.db

Sesiones = async_sessionmaker[AsyncSession]
CLAVE = "Actual12345"


def ahora() -> datetime:
    return datetime.now(UTC)


async def sembrar(session_factory: Sesiones, rol: Rol = Rol.PRESTADOR) -> Usuario:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        u = await uow.usuarios.add(
            Usuario(
                email=f"supresion.{uuid.uuid4().hex[:8]}@example.com",
                password_hash=FakePasswordHasher().hash(CLAVE),
                nombre_completo="Persona Real",
                rol=rol,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=ahora(),
            )
        )
        await uow.usuarios.actualizar_razon_social(u.id, "Tayrona SAS")  # type: ignore[arg-type]
        await uow.commit()
    return u


def suprimir(session_factory: Sesiones) -> SuprimirDatos:
    return SuprimirDatos(
        uow=SqlAlchemyUnitOfWork(session_factory),
        hasher=FakePasswordHasher(),
        almacen=FakeAlmacenDocumentos(),
        revocacion=FakeRevocacion(),
        reloj=ahora,
    )


async def test_supresion_cumple_las_restricciones_y_conserva_las_filas(
    session_factory: Sesiones,
) -> None:
    u = await sembrar(session_factory)
    assert u.id is not None
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        documento = await uow.documentos.agregar(
            DocumentoVerificacion(
                usuario_id=u.id,
                tipo_documento=TipoDocumento.RUT,
                objeto_s3=f"{u.id}/RUT/{uuid.uuid4()}.pdf",
                tipo_contenido="application/pdf",
                tamano_bytes=10,
            )
        )
        await uow.documentos.marcar_revisado(
            documento.id,  # type: ignore[arg-type]
            EstadoDocumento.RECHAZADO,
            u.id,
            ahora(),
            "Ilegible, escribir a persona.real@example.com",
        )
        await uow.commit()

    await suprimir(session_factory).execute(
        SuprimirDatosCommand(usuario_id=u.id, password=CLAVE, ip_origen="190.24.10.5")
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        final = await uow.usuarios.find_by_id(u.id)
        assert await uow.usuarios.find_by_email(Email(u.email)) is None
        [conservado] = await uow.documentos.historial(u.id)
    assert final is not None
    assert final.email == f"suprimido+{u.id}@invalid"
    assert (final.nombre_completo, final.razon_social, final.activo) == (
        "Usuario suprimido",
        None,
        False,
    )
    assert final.suprimido
    # La prueba del consentimiento se conserva (C-01): no es un dato de contacto.
    assert final.habeas_data_aceptado is True
    assert conservado.id == documento.id
    assert conservado.motivo_rechazo is None

    async with session_factory() as session:
        filas = (
            await session.scalars(
                select(BitacoraAuditoria).where(
                    BitacoraAuditoria.usuario_id == u.id,
                    BitacoraAuditoria.accion == "DATA_SUPPRESSION",
                )
            )
        ).all()
        eventos = (
            await session.scalars(
                select(Outbox).where(
                    Outbox.event_type == "prestador.suspendido",
                    Outbox.sobre["payload"]["usuario_id"].astext == str(u.id),
                )
            )
        ).all()
    [fila] = filas
    assert u.email not in str(fila.detalles)
    assert "Persona Real" not in str(fila.detalles)
    assert len(eventos) == 1


async def test_se_excluye_de_la_cola_y_el_correo_queda_libre(session_factory: Sesiones) -> None:
    u = await sembrar(session_factory)
    otro = await sembrar(session_factory)
    assert u.id is not None

    await suprimir(session_factory).execute(
        SuprimirDatosCommand(usuario_id=u.id, password=CLAVE, ip_origen=None)
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        cola = await uow.documentos.listar_prestadores(FiltroPrestadores(tamano=100))
    ids = {r.usuario_id for r in cola.items}
    assert u.id not in ids
    assert otro.id in ids

    nueva = await RegistrarUsuario(
        uow=SqlAlchemyUnitOfWork(session_factory), hasher=FakePasswordHasher(), reloj=ahora
    ).execute(
        RegistrarUsuarioCommand(
            email=u.email,
            password=CLAVE,
            nombre_completo="Persona Nueva",
            rol=Rol.TURISTA,
            habeas_data_aceptado=True,
            es_mayor_de_edad=True,
            ip_origen=None,
        )
    )
    assert nueva.id != u.id


async def test_repetir_la_supresion_terminada_es_contrasena_incorrecta(
    session_factory: Sesiones,
) -> None:
    u = await sembrar(session_factory)
    assert u.id is not None
    cmd = SuprimirDatosCommand(usuario_id=u.id, password=CLAVE, ip_origen=None)
    await suprimir(session_factory).execute(cmd)

    with pytest.raises(CredencialesInvalidasError):
        await suprimir(session_factory).execute(cmd)


async def test_la_version_empieza_en_1_y_sube_con_cada_edicion(session_factory: Sesiones) -> None:
    u = await sembrar(session_factory)
    assert u.id is not None and u.version == 1
    editar = EditarPerfil(uow=SqlAlchemyUnitOfWork(session_factory))

    editado = await editar.execute(
        EditarPerfilCommand(
            usuario_id=u.id,
            nombre="Otro Nombre",
            idioma=Idioma.EN,
            version_esperada=1,
            ip_origen=None,
        )
    )
    assert (editado.version, editado.nombre_completo, editado.idioma) == (
        2,
        "Otro Nombre",
        Idioma.EN,
    )

    with pytest.raises(VersionConflictoError):
        await editar.execute(
            EditarPerfilCommand(
                usuario_id=u.id, nombre="Tercero", idioma=None, version_esperada=1, ip_origen=None
            )
        )

    sin_cambios = await editar.execute(
        EditarPerfilCommand(
            usuario_id=u.id, nombre="Otro Nombre", idioma=None, version_esperada=1, ip_origen=None
        )
    )
    assert sin_cambios.version == 2

    async with session_factory() as session:
        modelo = await session.get(UsuarioModel, u.id)
    assert modelo is not None
    assert modelo.version == 2
