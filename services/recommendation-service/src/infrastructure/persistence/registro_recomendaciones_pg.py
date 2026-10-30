import logging
from collections.abc import Sequence

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.application.ports.errores import DependenciaNoDisponibleError
from src.domain.recomendacion import RegistroRecomendacion
from src.infrastructure.persistence.modelos import RecomendacionLogModelo

logger = logging.getLogger(__name__)


class RegistroRecomendacionesPostgres:
    """Implementa RegistroRecomendaciones sobre recommendation_db."""

    def __init__(self, motor: AsyncEngine) -> None:
        self._sesiones = async_sessionmaker[AsyncSession](motor, expire_on_commit=False)

    async def registrar(self, registros: Sequence[RegistroRecomendacion]) -> None:
        if not registros:
            return
        try:
            # Una sola transacción: o quedan todas las recomendaciones de la respuesta o ninguna.
            async with self._sesiones.begin() as sesion:
                sesion.add_all(
                    RecomendacionLogModelo(
                        id=r.id,
                        conversacion_id=r.conversacion_id,
                        turista_id=r.turista_id,
                        servicio_id=r.servicio_id,
                        justificacion=r.justificacion,
                        herramientas_usadas=list(r.herramientas_usadas),
                        modelo=r.modelo,
                        fecha_generacion=r.fecha_generacion,
                    )
                    for r in registros
                )
        except (OperationalError, InterfaceError, OSError) as exc:
            # Solo fallas de conexión; una violación de restricción sigue siendo un error.
            logger.warning("PostgreSQL no responde al registrar recomendaciones")
            raise DependenciaNoDisponibleError("PostgreSQL no responde") from exc
