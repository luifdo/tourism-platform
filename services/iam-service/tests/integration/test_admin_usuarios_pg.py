"""Repositorio de usuarios para UC27 contra PostgreSQL (C-29)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Rol
from app.domain.value_objects.filtro_usuarios import FiltroUsuarios
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.models import Usuario as UsuarioModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.db

Sesiones = async_sessionmaker[AsyncSession]


def cuenta(email: str, nombre: str = "Prueba Admin", rol: Rol = Rol.TURISTA) -> Usuario:
    return Usuario(
        email=email,
        password_hash="$argon2id$fake",
        nombre_completo=nombre,
        rol=rol,
        habeas_data_aceptado=True,
        habeas_data_aceptado_en=datetime.now(UTC),
    )


async def sembrar(session_factory: Sesiones, *cuentas: Usuario) -> list[Usuario]:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        guardadas = [await uow.usuarios.add(c) for c in cuentas]
        await uow.commit()
    return guardadas


async def buscar(session_factory: Sesiones, **filtro: object) -> list[str]:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        pagina = await uow.usuarios.listar(FiltroUsuarios(**filtro))  # type: ignore[arg-type]
    return [u.email for u in pagina.items]


async def test_q_busca_literal_por_nombre_y_correo(session_factory: Sesiones) -> None:
    sufijo = uuid.uuid4().hex[:8]
    await sembrar(
        session_factory,
        cuenta(f"cien.{sufijo}@example.com", f"Oferta 100% {sufijo}"),
        cuenta(f"mil.{sufijo}@example.com", f"Oferta 1000 {sufijo}"),
        cuenta(f"guion_{sufijo}@example.com", f"Otra {sufijo}"),
        cuenta(f"guionx{sufijo}@example.com", f"Otra más {sufijo}"),
    )

    # Sin escapar, "%" y "_" serían comodines y traerían también las otras cuentas.
    assert await buscar(session_factory, q=f"100% {sufijo}") == [f"cien.{sufijo}@example.com"]
    assert await buscar(session_factory, q=f"guion_{sufijo}") == [f"guion_{sufijo}@example.com"]
    assert len(await buscar(session_factory, q=sufijo.upper())) == 4  # sin distinguir mayúsculas


async def test_filtros_total_y_paginacion(session_factory: Sesiones) -> None:
    sufijo = uuid.uuid4().hex[:8]
    a, b, c = await sembrar(
        session_factory,
        cuenta(f"a.{sufijo}@example.com", f"Pag {sufijo}", Rol.ENTIDAD),
        cuenta(f"b.{sufijo}@example.com", f"Pag {sufijo}", Rol.ENTIDAD),
        cuenta(f"c.{sufijo}@example.com", f"Pag {sufijo}", Rol.TURISTA),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        pagina = await uow.usuarios.listar(
            FiltroUsuarios(rol=Rol.ENTIDAD, activo=True, q=sufijo, pagina=2, tamano=1)
        )

    assert pagina.total == 2
    assert len(pagina.items) == 1
    assert pagina.items[0].email in {a.email, b.email}
    assert c.email not in await buscar(session_factory, q=sufijo, rol=Rol.ENTIDAD)


async def test_actualizar_rol_y_estado(session_factory: Sesiones) -> None:
    [creado] = await sembrar(session_factory, cuenta(f"upd.{uuid.uuid4().hex[:8]}@example.com"))
    assert creado.id is not None

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        bloqueado = await uow.usuarios.find_by_id_para_actualizar(creado.id)
        actualizado = await uow.usuarios.actualizar_rol_y_estado(creado.id, Rol.ENTIDAD, False)
        await uow.commit()

    assert bloqueado == creado
    assert (actualizado.rol, actualizado.activo) == (Rol.ENTIDAD, False)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.usuarios.find_by_id(creado.id) == actualizado
    assert replace(actualizado, rol=creado.rol, activo=True, actualizado_en=None) == replace(
        creado, actualizado_en=None
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Engine propio con commits reales: el bloqueo necesita dos transacciones."""
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


async def test_bloquear_admins_serializa_los_cambios_administrativos(engine: AsyncEngine) -> None:
    sesiones = build_session_factory(engine)
    sufijo = uuid.uuid4().hex[:8]
    admins = await sembrar(
        sesiones,
        cuenta(f"lock1.{sufijo}@example.com", rol=Rol.ADMIN),
        cuenta(f"lock2.{sufijo}@example.com", rol=Rol.ADMIN),
    )
    try:
        primero = SqlAlchemyUnitOfWork(sesiones)
        async with primero as uow:
            cuantos = await uow.usuarios.bloquear_admins_activos()
            assert cuantos >= 2

            async def segundo_cambio() -> int:
                async with SqlAlchemyUnitOfWork(sesiones) as otro:
                    return await otro.usuarios.bloquear_admins_activos()

            # El segundo cambio espera a que el primero termine: no cuentan los dos a la vez.
            tarea = asyncio.create_task(segundo_cambio())
            await asyncio.sleep(0.5)
            assert not tarea.done()
            await uow.usuarios.actualizar_rol_y_estado(admins[0].id, Rol.TURISTA, True)  # type: ignore[arg-type]
            await uow.commit()

        # Al liberarse, el segundo ve el conteo ya actualizado.
        assert await asyncio.wait_for(tarea, timeout=3) == cuantos - 1
    finally:
        async with sesiones() as session, session.begin():
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.id.in_([a.id for a in admins]))
            )
