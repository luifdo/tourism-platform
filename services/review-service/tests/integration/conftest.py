"""PostgreSQL real y efímero (testcontainers), con las migraciones aplicadas.

Requiere Docker. Si no está disponible, las pruebas de integración se omiten.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.config import get_settings

RAIZ = Path(__file__).resolve().parents[2]
IMAGEN = "postgres:16"


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
