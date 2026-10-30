from typing import Protocol
from uuid import UUID

from app.application.dto.contacto_usuario import ContactoUsuario


class DirectorioUsuarios(Protocol):
    async def contacto(self, usuario_id: UUID) -> ContactoUsuario | None:
        """Contacto según iam; None si el usuario no existe. Si iam no responde, lanza
        DependenciaNoDisponible (el consumidor reintenta)."""
        ...
