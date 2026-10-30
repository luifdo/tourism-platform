"""Puerto de persistencia `ElegibilidadRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.elegibilidad_resena import ElegibilidadResena


class ElegibilidadRepository(Protocol):
    async def obtener(self, turista_id: UUID, servicio_id: UUID) -> ElegibilidadResena | None: ...

    async def guardar(self, elegibilidad: ElegibilidadResena) -> None:
        """Nunca retrocede la última visita, aunque dos eventos se guarden a la vez."""
        ...
