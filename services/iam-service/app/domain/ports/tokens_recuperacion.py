import uuid
from datetime import timedelta
from typing import Protocol

# C-28: el enlace vale 30 minutos y entre dos correos a un usuario pasan al menos 60 s.
VALIDEZ_TOKEN = timedelta(minutes=30)
ESPERA_ENTRE_CORREOS = timedelta(seconds=60)


class TokensRecuperacion(Protocol):
    """Tokens de un solo uso de UC3. Solo se guarda su SHA-256, nunca el token en claro.

    Lanzan ServicioNoDisponibleError si el almacenamiento no responde.
    """

    async def reservar_envio(self, usuario_id: uuid.UUID) -> bool:
        """Inicia la espera entre correos. False si el usuario ya está dentro de ella."""
        ...

    async def guardar(self, token: str, usuario_id: uuid.UUID) -> None:
        """Guarda el token e invalida el anterior del usuario, si lo había."""
        ...

    async def consumir(self, token: str) -> uuid.UUID | None:
        """Devuelve el usuario y borra el token en un solo paso. None si no es válido."""
        ...

    async def descartar(self, usuario_id: uuid.UUID) -> None:
        """Borra el token vigente y la espera: no se pudo enviar el correo."""
        ...
