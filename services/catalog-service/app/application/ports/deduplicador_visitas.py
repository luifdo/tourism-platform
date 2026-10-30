from datetime import date
from typing import Protocol
from uuid import UUID


class DeduplicadorVisitas(Protocol):
    """Recuerda por 24 h que un visitante ya pidió la ruta a un servicio ese día.

    El visitante se identifica por su IP, pero solo se guarda un hash con una sal que
    cambia cada día: no se puede recuperar el IP ni seguir a alguien entre días.
    """

    async def primera_vez(self, ip: str, servicio_id: UUID, fecha: date) -> bool | None:
        """True la primera vez ese día; False si ya contó; None si no se pudo saber."""
        ...

    async def olvidar(self, ip: str, servicio_id: UUID, fecha: date) -> None:
        """Deshace `primera_vez` (p. ej. si el servicio no existe y no se contó)."""
        ...
