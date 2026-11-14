"""Puerto de lectura `ConsultaResenas`: listas y resumen, sin bloquear filas.

Las escrituras usan la unidad de trabajo; estas consultas tienen su propio puerto para leer
solo lo que muestra cada vista.
"""

from typing import Protocol
from uuid import UUID

from app.application.dto.orden_resenas import OrdenResenas
from app.application.dto.pagina_moderacion import PaginaModeracion
from app.application.dto.pagina_resenas import PaginaResenas
from app.application.dto.resumen_servicio import ResumenServicio
from app.application.dto.servicio_pendiente import ServicioPendiente
from app.domain.entities.resena import Resena
from app.domain.value_objects.estado_resena import EstadoResena


class ConsultaResenas(Protocol):
    async def de_servicio(
        self, servicio_id: UUID, orden: OrdenResenas, pagina: int, tamano: int
    ) -> PaginaResenas:
        """Solo las publicadas."""
        ...

    async def resumen(self, servicio_id: UUID) -> ResumenServicio: ...

    async def publica(self, resena_id: UUID) -> Resena | None:
        """La reseña si está publicada; None si no existe o no está visible."""
        ...

    async def del_turista(self, turista_id: UUID, pagina: int, tamano: int) -> PaginaResenas:
        """Todas las suyas, en cualquier estado, de la más reciente a la más vieja."""
        ...

    async def pendientes(self, turista_id: UUID) -> list[ServicioPendiente]:
        """Servicios con reserva finalizada y sin reseña suya, de la visita más reciente."""
        ...

    async def dueno_de(self, servicio_id: UUID) -> UUID | None:
        """Usuario prestador dueño del servicio, si review lo conoce."""
        ...

    async def del_prestador(
        self,
        prestador_usuario_id: UUID,
        servicio_id: UUID | None,
        sin_respuesta: bool,
        pagina: int,
        tamano: int,
    ) -> PaginaResenas:
        """Publicadas y en revisión de los servicios de los que es dueño."""
        ...

    async def cola_moderacion(
        self, estado: EstadoResena | None, pagina: int, tamano: int
    ) -> PaginaModeracion:
        """Reseñas que esperan al Administrador, con sus reportes sin resolver: primero las
        en revisión, luego las más reportadas y, a igualdad, la más antigua."""
        ...
