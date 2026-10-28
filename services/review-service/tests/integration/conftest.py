"""PostgreSQL real y efímero (testcontainers), con las migraciones aplicadas.

Requiere Docker. Si no está disponible, las pruebas de integración se omiten.
"""

import os
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

RAIZ = Path(__file__).resolve().parents[2]
IMAGEN = "postgres:16"
TABLAS_DE_PRUEBA = (
    "idempotencia",
    "outbox",
    "evento_procesado",
    "servicio_dueno",
    "elegibilidad_resena",
    "reporte_resena",
    "resena",
)


def alembic_config() -> Config:
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    return config


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    try:
        from testcontainers.postgres import PostgresContainer

        contenedor = PostgresContainer(IMAGEN, driver="asyncpg").start()
    except Exception as exc:  # Docker apagado o no instalado
        pytest.skip(f"Docker no disponible para las pruebas de integración: {exc}")
    url = contenedor.get_connection_url()
    anterior = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    command.upgrade(alembic_config(), "head")
    yield url
    contenedor.stop()
    if anterior is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = anterior
    get_settings.cache_clear()


@pytest.fixture
def alembic_cfg(database_url: str) -> Config:
    return alembic_config()


@pytest.fixture
async def engine(
    database_url: str, validar_evento: Callable[[dict[str, Any]], None]
) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(database_url)
    yield engine
    async with engine.begin() as conn:
        # Contrato de eventos: todo lo que la prueba dejó en el outbox es lo que el servicio
        # publicaría; debe cumplir contracts/events/ (envelope.v1 y el esquema del payload).
        for (sobre,) in await conn.execute(text("SELECT sobre FROM outbox ORDER BY creado_en")):
            validar_evento(sobre)
        await conn.execute(text(f"TRUNCATE {', '.join(TABLAS_DE_PRUEBA)} CASCADE"))
    await engine.dispose()


@pytest.fixture
def sesiones(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return build_session_factory(engine)


@pytest.fixture
def uow(sesiones: async_sessionmaker[AsyncSession]) -> Callable[[], SqlUnidadDeTrabajo]:
    return lambda: SqlUnidadDeTrabajo(sesiones)
