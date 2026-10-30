import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.application.use_cases.registrar_usuario import RegistrarUsuario, RegistrarUsuarioCommand
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import UsuarioYaExisteError
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import Idioma, ResultadoAuditoria, Rol
from app.infrastructure.persistence.models import BitacoraAuditoria
from app.infrastructure.persistence.models import Usuario as UsuarioModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher

pytestmark = pytest.mark.db

EMAIL = "integracion.repo@example.com"


def nuevo_usuario(email: str = EMAIL) -> Usuario:
    return Usuario(
        email=email,
        password_hash="$argon2id$fake",
        nombre_completo="Prueba Integración",
        rol=Rol.TURISTA,
        habeas_data_aceptado=True,
        habeas_data_aceptado_en=datetime.now(UTC),
    )


async def test_add_y_find_by_email(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        creado = await uow.usuarios.add(nuevo_usuario())
        await uow.commit()

    assert creado.id is not None
    assert creado.creado_en is not None
    assert creado.actualizado_en is not None

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        encontrado = await uow.usuarios.find_by_email(Email(EMAIL.upper()))
        ausente = await uow.usuarios.find_by_email(Email("nadie@example.com"))

    assert encontrado == creado
    assert ausente is None


async def test_email_duplicado_en_la_base_es_usuario_ya_existe(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.usuarios.add(nuevo_usuario())
        await uow.commit()

    # Simula la carrera: el segundo registro no pasa por find_by_email y choca con la UNIQUE.
    with pytest.raises(UsuarioYaExisteError):
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.usuarios.add(nuevo_usuario())


async def test_usuario_y_auditoria_en_la_misma_transaccion(
    connection: AsyncConnection, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registrar = RegistrarUsuario(
        uow=SqlAlchemyUnitOfWork(session_factory),
        hasher=Argon2PasswordHasher(),
        reloj=lambda: datetime.now(UTC),
    )

    usuario = await registrar.execute(
        RegistrarUsuarioCommand(
            email=EMAIL,
            password="Tayrona2026",
            nombre_completo="Prueba Integración",
            rol=Rol.PRESTADOR,
            habeas_data_aceptado=True,
            es_mayor_de_edad=True,
            ip_origen="190.0.0.1",
        )
    )

    fila = (
        await connection.execute(
            select(BitacoraAuditoria).where(BitacoraAuditoria.usuario_id == usuario.id)
        )
    ).one()
    assert fila.accion == "USER_REGISTER"
    assert fila.resultado is ResultadoAuditoria.EXITO
    assert str(fila.ip_origen) == "190.0.0.1"
    assert fila.detalles == {"rol": "Prestador"}


async def test_sin_commit_no_se_guarda_ni_el_usuario_ni_la_auditoria(
    connection: AsyncConnection, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        creado = await uow.usuarios.add(nuevo_usuario())
        await uow.auditoria.registrar(
            accion="USER_REGISTER",
            resultado=ResultadoAuditoria.EXITO,
            usuario_id=creado.id,
            ip_origen=None,
            detalles={},
        )
        # Sale del bloque sin commit(): rollback de ambos.

    usuarios = await connection.scalar(
        select(func.count()).select_from(UsuarioModel).where(UsuarioModel.email == EMAIL)
    )
    auditoria = await connection.scalar(
        select(func.count())
        .select_from(BitacoraAuditoria)
        .where(BitacoraAuditoria.usuario_id == creado.id)
    )
    assert (usuarios, auditoria) == (0, 0)


async def test_find_by_id_e_idioma(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        por_defecto = await uow.usuarios.add(nuevo_usuario())
        en_ingles = await uow.usuarios.add(
            replace(nuevo_usuario("integracion.en@example.com"), idioma=Idioma.EN)
        )
        await uow.commit()
    assert por_defecto.id is not None
    assert en_ingles.id is not None

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.usuarios.find_by_id(por_defecto.id) == por_defecto
        assert (await uow.usuarios.find_by_id(en_ingles.id)).idioma is Idioma.EN  # type: ignore[union-attr]
        assert await uow.usuarios.find_by_id(uuid.uuid4()) is None

    assert por_defecto.idioma is Idioma.ES


async def test_la_base_rechaza_un_idioma_no_soportado(connection: AsyncConnection) -> None:
    async with SqlAlchemyUnitOfWork(
        async_sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    ) as uow:
        creado = await uow.usuarios.add(nuevo_usuario())
        await uow.commit()

    savepoint = await connection.begin_nested()
    with pytest.raises(IntegrityError, match="ck_usuario_idioma_valido"):
        await connection.execute(
            text("UPDATE usuario SET idioma = 'fr' WHERE id = :id"), {"id": creado.id}
        )
    await savepoint.rollback()
