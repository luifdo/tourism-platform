"""Puerto de persistencia `DisponibilidadRepository` (adaptador en persistence/repositorios)."""

from datetime import date
from typing import Protocol
from uuid import UUID

from app.domain.entities.disponibilidad_dia import DisponibilidadDia


class DisponibilidadRepository(Protocol):
    async def obtener(self, servicio_id: UUID, fecha: date) -> DisponibilidadDia | None: ...

    async def guardar(self, dia: DisponibilidadDia) -> None:
        """Inserta o actualiza; si la fila de la base tiene una versión más nueva, no la toca."""
        ...

    async def borrar_anteriores(self, fecha: date) -> int:
        """Borra los días anteriores a `fecha`; devuelve cuántos."""
        ...
