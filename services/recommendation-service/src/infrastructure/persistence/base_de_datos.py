import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)


def crear_motor(db_url: str) -> AsyncEngine:
    return create_async_engine(db_url, pool_pre_ping=True)


class SondaPostgres:
    """Implementa Sonda ejecutando SELECT 1 contra recommendation_db."""

    def __init__(self, motor: AsyncEngine, timeout_segundos: float = 2.0) -> None:
        self._motor = motor
        self._timeout_segundos = timeout_segundos

    async def ping(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout_segundos):
                async with self._motor.connect() as conexion:
                    await conexion.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError, TimeoutError):
            logger.warning("PostgreSQL no responde", exc_info=True)
            return False
        return True
