import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.infrastructure.persistence.database import Base, build_engine

# modelos/ no tiene __init__.py: se importa cada archivo para registrar su tabla en Base.metadata.
from app.infrastructure.persistence.modelos import (  # noqa: F401
    alerta_oficial,
    atractivo_servicio,
    calificacion_resena,
    evento_procesado,
    outbox,
    prestador_perfil,
    reserva_proyeccion,
    zona,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = get_settings().database_url
# En k8s cada pod de la API migra al arrancar (initContainer). Con este candado de PostgreSQL
# los demás esperan a que termine el primero y luego ven que ya está en head. Es de
# transacción: se suelta solo al confirmar o si el proceso muere.
CANDADO_MIGRACIONES = 820_002


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        connection.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": CANDADO_MIGRACIONES})
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = build_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
