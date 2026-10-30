import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.infrastructure.persistence.database import build_engine
from app.infrastructure.persistence.models import Outbox


@pytest.fixture
async def connection() -> AsyncIterator[AsyncConnection]:
    """Conexión dentro de una transacción que se deshace al terminar cada prueba.

    Así no quedan filas: la bitácora no admite DELETE y su FK con RESTRICT impide borrar
    los usuarios que referencia. Si PostgreSQL no responde, la prueba se omite.
    """
    engine = build_engine(get_settings().database_url)
    try:
        conn = await asyncio.wait_for(engine.connect(), timeout=3)
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL no responde: {type(exc).__name__}")

    transaction = await conn.begin()
    try:
        yield conn
    finally:
        await transaction.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
async def sin_pendientes_ajenos(connection: AsyncConnection) -> None:
    """Oculta los eventos pendientes que ya había en la base de desarrollo.

    El relay procesa todo lo pendiente: sin esto, un evento dejado por el smoke test o por usar
    el servicio sin el worker le cambia el resultado a la prueba. Se deshace con la transacción.
    """
    await connection.execute(
        update(Outbox).where(Outbox.publicado_en.is_(None)).values(publicado_en=func.now())
    )


@pytest.fixture(scope="session")
def rabbitmq_url() -> Iterator[str]:
    """RabbitMQ efímero (testcontainers, misma imagen que infra/docker-compose.yml).

    No usa el broker de docker-compose.dev.yml: las pruebas de la DLQ dejarían mensajes en
    `turismo.dead-letter`. Si Docker no está disponible, la prueba se omite.
    """
    try:
        from testcontainers.community.rabbitmq import RabbitMqContainer

        contenedor = RabbitMqContainer("rabbitmq:4-management").start()
    except Exception as exc:
        pytest.skip(f"Docker no disponible para RabbitMQ: {type(exc).__name__}")
    host = contenedor.get_container_host_ip()
    yield f"amqp://guest:guest@{host}:{contenedor.get_exposed_port(5672)}/"
    contenedor.stop()


@pytest.fixture
def session_factory(connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    # El commit() de cada sesión libera un SAVEPOINT; la transacción externa sigue abierta.
    return async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
