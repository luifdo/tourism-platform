from typing import Protocol
from uuid import UUID

from src.domain.conversacion import Conversacion


class RepositorioSesiones(Protocol):
    """Guarda la conversación reciente de cada sesión durante 24 horas."""

    async def obtener(self, conversacion_id: UUID) -> Conversacion | None:
        """Devuelve None si la conversación no existe o ya expiró."""
        ...

    async def guardar(self, conversacion: Conversacion) -> None: ...
