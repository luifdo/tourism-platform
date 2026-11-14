from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.repositorios.elegibilidad_repository import (
    SqlElegibilidadRepository,
)
from app.infrastructure.persistence.repositorios.eventos_procesados import SqlEventosProcesados
from app.infrastructure.persistence.repositorios.outbox import SqlOutbox
from app.infrastructure.persistence.repositorios.reporte_repository import SqlReporteRepository
from app.infrastructure.persistence.repositorios.resena_repository import SqlResenaRepository
from app.infrastructure.persistence.repositorios.servicio_dueno_repository import (
    SqlServicioDuenoRepository,
)


class SqlUnidadDeTrabajo:
    """Implementa UnidadDeTrabajo: una sesión y una transacción por operación."""

    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._sesiones()
        await self._session.begin()
        self.resenas = SqlResenaRepository(self._session)
        self.reportes = SqlReporteRepository(self._session)
        self.elegibilidades = SqlElegibilidadRepository(self._session)
        self.servicios = SqlServicioDuenoRepository(self._session)
        self.eventos_procesados = SqlEventosProcesados(self._session)
        self.outbox = SqlOutbox(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if self._session.in_transaction():
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def confirmar(self) -> None:
        assert self._session is not None
        await self._session.commit()
