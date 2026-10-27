from types import TracebackType
from typing import Protocol, Self

from app.domain.ports.alerta_repository import AlertaRepository
from app.domain.ports.calificacion_repository import CalificacionRepository
from app.domain.ports.disponibilidad_repository import DisponibilidadRepository
from app.domain.ports.eventos_procesados import EventosProcesados
from app.domain.ports.outbox import Outbox
from app.domain.ports.prestador_repository import PrestadorRepository
from app.domain.ports.reserva_proyeccion_repository import ReservaProyeccionRepository
from app.domain.ports.servicio_repository import ServicioRepository
from app.domain.ports.zona_repository import ZonaRepository


class UnidadDeTrabajo(Protocol):
    """Una transacción sobre catalog_db: los repositorios comparten la misma sesión.

    Los repositorios solo declaran lo que necesitan las reglas de escritura; las consultas de
    lectura (búsqueda, mapa, analítica) tienen sus propios puertos.

    Al salir del bloque sin `confirmar()` se deshacen los cambios, incluidos los eventos del
    outbox: un evento existe solo si su cambio se confirmó.
    """

    prestadores: PrestadorRepository
    servicios: ServicioRepository
    zonas: ZonaRepository
    alertas: AlertaRepository
    reservas: ReservaProyeccionRepository
    calificaciones: CalificacionRepository
    disponibilidad: DisponibilidadRepository
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
