"""Puerto de persistencia `ReservaProyeccionRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.reserva_proyeccion import ReservaProyeccion


class ReservaProyeccionRepository(Protocol):
    async def obtener(self, reserva_id: UUID) -> ReservaProyeccion | None: ...

    async def guardar(self, reserva: ReservaProyeccion) -> None: ...
