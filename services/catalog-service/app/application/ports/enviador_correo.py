from typing import Protocol

from app.application.dto.correo import Correo


class EnviadorCorreo(Protocol):
    async def enviar(self, correo: Correo) -> None:
        """Vuelve cuando el servidor de correo lo aceptó; si no, lanza una excepción."""
        ...
