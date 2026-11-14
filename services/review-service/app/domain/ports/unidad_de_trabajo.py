from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from app.domain.ports.elegibilidad_repository import ElegibilidadRepository
from app.domain.ports.eventos_procesados import EventosProcesados
from app.domain.ports.outbox import Outbox
from app.domain.ports.reporte_repository import ReporteRepository
from app.domain.ports.resena_repository import ResenaRepository
from app.domain.ports.servicio_dueno_repository import ServicioDuenoRepository


class UnidadDeTrabajo(Protocol):
    """Una transacción sobre review_db: los repositorios comparten la misma sesión.

    Los repositorios solo declaran lo que necesitan las reglas de escritura; las consultas de
    lectura (listas, resumen, cola de moderación) tienen sus propios puertos.

    Al salir del bloque sin `confirmar()` se deshacen los cambios, incluidos los eventos del
    outbox: un evento existe solo si su cambio se confirmó.
    """

    resenas: ResenaRepository
    reportes: ReporteRepository
    elegibilidades: ElegibilidadRepository
    servicios: ServicioDuenoRepository
    eventos_procesados: EventosProcesados
    outbox: Outbox

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def confirmar(self) -> None: ...


# Cada caso de uso abre una unidad de trabajo nueva por operación.
FabricaUnidadDeTrabajo = Callable[[], UnidadDeTrabajo]
