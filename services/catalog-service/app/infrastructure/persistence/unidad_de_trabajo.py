from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.repositorios.alerta_repository import SqlAlertaRepository
from app.infrastructure.persistence.repositorios.calificacion_repository import (
    SqlCalificacionRepository,
)
from app.infrastructure.persistence.repositorios.disponibilidad_repository import (
    SqlDisponibilidadRepository,
)
from app.infrastructure.persistence.repositorios.eventos_procesados import SqlEventosProcesados
from app.infrastructure.persistence.repositorios.outbox import SqlOutbox
from app.infrastructure.persistence.repositorios.prestador_repository import (
    SqlPrestadorRepository,
)
from app.infrastructure.persistence.repositorios.reserva_proyeccion_repository import (
    SqlReservaProyeccionRepository,
)
from app.infrastructure.persistence.repositorios.servicio_repository import SqlServicioRepository
from app.infrastructure.persistence.repositorios.zona_repository import SqlZonaRepository


class SqlUnidadDeTrabajo:
    """Implementa UnidadDeTrabajo: una sesión y una transacción por operación."""

    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._sesiones()
        await self._session.begin()
        self.prestadores = SqlPrestadorRepository(self._session)
        self.servicios = SqlServicioRepository(self._session)
        self.zonas = SqlZonaRepository(self._session)
        self.alertas = SqlAlertaRepository(self._session)
        self.reservas = SqlReservaProyeccionRepository(self._session)
        self.calificaciones = SqlCalificacionRepository(self._session)
        self.disponibilidad = SqlDisponibilidadRepository(self._session)
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
