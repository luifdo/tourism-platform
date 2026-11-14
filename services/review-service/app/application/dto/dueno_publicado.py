from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DuenoPublicado:
    """El dueño de un servicio según `servicio.publicado`, con la versión del servicio."""

    event_id: UUID
    servicio_id: UUID
    prestador_usuario_id: UUID
    version: int
