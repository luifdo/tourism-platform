"""Puerto de persistencia `ServicioDuenoRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.servicio_dueno import ServicioDueno


class ServicioDuenoRepository(Protocol):
    async def obtener(self, servicio_id: UUID) -> ServicioDueno | None: ...

    async def guardar(self, servicio: ServicioDueno) -> None:
        """No escribe si la base ya tiene una versión igual o mayor (eventos en desorden)."""
        ...
