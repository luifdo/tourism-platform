"""Pruebas de integración contra un Postgres real.

Levántelo con `python scripts/postgres_pruebas.py subir` (puerto 5433). Si no responde,
estas pruebas se saltan con un aviso en vez de fallar. Otra base: TEST_DATABASE_URL.

Cada sesión de pruebas parte de una base vacía y migrada (downgrade a base + upgrade head),
y cada prueba corre dentro de una transacción que se deshace al final.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from config import Configuracion
from domain.reglas import ZONA
from infrastructure.http import demo
from infrastructure.persistence.db import verificar_conexion
from infrastructure.persistence.tablas import disponibilidad_cupo, evento_outbox, servicio_ref, solicitud_reserva
from infrastructure.reloj import RelojFijo
from main import contenedor_postgres, crear_app

RAIZ = Path(__file__).resolve().parents[2]
AHORA = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)  # reloj fijo de las pruebas de API
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


# ---------- API completa sobre Postgres ----------

async def _limpiar_demo(motor):
    async with motor.begin() as con:
        await con.execute(delete(evento_outbox))  # base de pruebas: las pruebas de API no corren en paralelo
        for tabla in (solicitud_reserva, disponibilidad_cupo, servicio_ref):
            await con.execute(delete(tabla).where(tabla.c.servicio_id == demo.SERVICIO_DEMO))


@pytest.fixture
def outbox(motor):
    """Lee los sobres pendientes de evento_outbox, en el orden en que se produjeron."""
    async def leer() -> list[dict]:
        async with motor.connect() as con:
            filas = await con.execute(
                select(evento_outbox.c.sobre).where(evento_outbox.c.publicado_en.is_(None)).order_by(evento_outbox.c.creado_en)
            )
            return [f[0] for f in filas]
    return leer


@pytest.fixture
async def cliente(base_migrada, motor):
    """Cliente HTTP de la app en modo postgres, con el servicio de la demo y 30 días de 10 cupos
    (desde el 2 de noviembre) cargados por los propios casos de uso. Borra todo al terminar."""
    config = Configuracion(modo_persistencia="postgres", database_url=base_migrada, datos_demo=False)
    contenedor = contenedor_postgres(config, RelojFijo(AHORA))
    await _limpiar_demo(motor)  # por si una corrida anterior se interrumpió
    await demo.cargar_datos_demo(contenedor)
    async with motor.begin() as con:
        await con.execute(delete(evento_outbox))  # solo cuentan los eventos de la prueba
    app = crear_app(config, contenedor)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://booking") as c:
            c.contenedor = contenedor
            yield c
    finally:
        await contenedor.extras["motor"].dispose()
        await _limpiar_demo(motor)
