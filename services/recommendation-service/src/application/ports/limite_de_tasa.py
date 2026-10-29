from typing import Protocol
from uuid import UUID


class LimiteDeTasa(Protocol):
    """Cuántos mensajes puede enviar un turista por ventana de tiempo (Guía Técnica §6)."""

    async def permitir(self, turista_id: UUID) -> bool:
        """Cuenta el mensaje y dice si está dentro del límite."""
        ...
