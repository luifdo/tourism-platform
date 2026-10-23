"""Entorno de Alembic para booking_db.

* La URL sale de DATABASE_URL (config.py). Las pruebas pueden pasar otra con
  `alembic_cfg.attributes["database_url"]`.
* `target_metadata` son las tablas de infrastructure/persistence/tablas.py: es lo que
  usa `alembic revision --autogenerate` para comparar el código con la base.
* El driver es asíncrono (asyncpg), así que las migraciones corren dentro de `asyncio.run`.
"""

import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from config import Configuracion
from infrastructure.persistence.tablas import metadata

config = context.config
target_metadata = metadata


def _url() -> str:
    return config.attributes.get("database_url") or Configuracion().database_url


def _configurar(conexion) -> None:
    context.configure(
        connection=conexion,
        target_metadata=target_metadata,
        compare_type=True,  # que autogenerate también detecte cambios de tipo de columna
        compare_server_default=True,
    )


def migraciones_sin_conexion() -> None:
    """`alembic upgrade head --sql`: imprime el SQL en vez de ejecutarlo (útil para revisarlo)."""
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def migraciones_con_conexion() -> None:
    motor = create_async_engine(_url())
    async with motor.connect() as conexion:
        await conexion.run_sync(_configurar)
        await conexion.run_sync(lambda _: context.run_migrations())
        await conexion.commit()
    await motor.dispose()


if context.is_offline_mode():
    migraciones_sin_conexion()
else:
    asyncio.run(migraciones_con_conexion())
