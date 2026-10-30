"""Puerto de persistencia `ResenaRepository` (adaptador en persistence/repositorios)."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.resena import Resena


class ResenaRepository(Protocol):
    async def obtener(self, resena_id: UUID) -> Resena | None:
        """Bloquea la fila hasta el final de la transacción (ediciones concurrentes)."""
        ...

    async def obtener_de_turista(self, turista_id: UUID, servicio_id: UUID) -> Resena | None: ...

    async def guardar(self, resena: Resena) -> None:
        """Lanza `YaResenado` si el turista ya tiene otra reseña del servicio."""
        ...
