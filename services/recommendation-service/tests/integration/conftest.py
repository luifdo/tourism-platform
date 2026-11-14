"""Pruebas contra PostgreSQL y Valkey reales, los del docker-compose del servicio.

Se omiten si no responden. Para correrlas: `docker compose up -d postgres valkey`.
"""

import os

import pytest

from src.infrastructure.persistence.base_de_datos import SondaPostgres, crear_motor
from src.infrastructure.persistence.sesiones_valkey import SondaValkey, crear_cliente_valkey

DB_URL = os.getenv(
    "TEST_DB_URL", "postgresql+psycopg://turismo:turismo@localhost:5434/recommendation_db"
)
# Base 15 de Valkey: las pruebas la vacían sin tocar las sesiones de desarrollo (base 0).
VALKEY_URL = os.getenv("TEST_VALKEY_URL", "redis://localhost:6380/15")


@pytest.fixture
def urls_reales() -> tuple[str, str]:
    return DB_URL, VALKEY_URL


@pytest.fixture
async def motor():
    motor = crear_motor(DB_URL)
    if not await SondaPostgres(motor).ping():
        await motor.dispose()
        pytest.skip(f"PostgreSQL no responde en {DB_URL}")
    yield motor
    await motor.dispose()


@pytest.fixture
async def valkey():
    cliente = crear_cliente_valkey(VALKEY_URL)
    if not await SondaValkey(cliente).ping():
        await cliente.aclose()
        pytest.skip(f"Valkey no responde en {VALKEY_URL}")
    yield cliente
    await cliente.flushdb()
    await cliente.aclose()
