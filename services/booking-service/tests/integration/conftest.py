"""Pruebas de integración contra un Postgres real.

Levántelo con `python scripts/postgres_pruebas.py subir` (puerto 5433). Si no responde,
estas pruebas se saltan con un aviso en vez de fallar. Otra base: TEST_DATABASE_URL.

Cada sesión de pruebas parte de una base vacía y migrada (downgrade a base + upgrade head),
y cada prueba corre dentro de una transacción que se deshace al final.
"""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from config import Configuracion
from infrastructure.persistence.db import verificar_conexion

RAIZ = Path(__file__).resolve().parents[2]
URL = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://booking:booking@127.0.0.1:5433/booking_db")


def configuracion_alembic() -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.attributes["database_url"] = URL
    return cfg


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(pytest.mark.integracion)


@pytest.fixture(scope="session")
def base_migrada() -> str:
    motor = create_async_engine(URL)
    disponible = asyncio.run(_responde(motor))
    if not disponible:
        pytest.skip(f"Postgres no responde en {URL}. Levántelo con: python scripts/postgres_pruebas.py subir")
    cfg = configuracion_alembic()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return URL


async def _responde(motor) -> bool:
    try:
        return await verificar_conexion(motor)
    finally:
        await motor.dispose()


@pytest.fixture
async def conexion(base_migrada):
    """Una conexión con una transacción abierta que se deshace al terminar la prueba."""
    motor = create_async_engine(base_migrada)
    async with motor.connect() as con:
        transaccion = await con.begin()
        yield con
        await transaccion.rollback()
    await motor.dispose()


@pytest.fixture
async def motor(base_migrada):
    """Para pruebas con varias transacciones que se confirman de verdad (concurrencia).
    Lo que confirmen queda en la base: cada prueba borra lo suyo al terminar."""
    m = create_async_engine(base_migrada)
    yield m
    await m.dispose()


@pytest.fixture
def alembic_cfg(base_migrada) -> Config:
    return configuracion_alembic()


@pytest.fixture
def config_db(base_migrada) -> Configuracion:
    return Configuracion(database_url=base_migrada)
