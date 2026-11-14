import uuid
from datetime import datetime
from typing import Protocol

from app.domain.value_objects.sesion import ResultadoRotacion, SesionCreada


class SesionesRenovacion(Protocol):
    """Familias de refresh tokens (C-20, C-60).

    Lanza ServicioNoDisponibleError si no puede comprobarlo: nunca asume que un token sirve.
    """

    async def crear(
        self, usuario_id: uuid.UUID, familia: str, emitido_en: datetime
    ) -> SesionCreada:
        """Crea la familia y su primer token.

        `emitido_en` es el iat del access token con ese sid: así los dos quedan del mismo lado
        de una marca revocado-desde (C-21).
        """
        ...

    async def rotar(self, refresh_token: str) -> ResultadoRotacion:
        """Cambia el token por uno nuevo en una sola operación atómica.

        Revoca la familia si el token ya fue rotado o si la cuenta tiene una marca revocado-desde
        igual o posterior a la última renovación.
        """
        ...

    async def revocar_familia(self, familia: str) -> None:
        """Revoca los refresh tokens de la sesión y los access tokens con ese sid."""
        ...
