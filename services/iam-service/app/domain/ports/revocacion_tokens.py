import uuid
from datetime import datetime
from typing import Protocol


class RevocacionTokens(Protocol):
    """Revocación de tokens por jti (logout) y por usuario (cambio de rol o desactivación).

    Lanza ServicioNoDisponibleError si no puede comprobarlo: nunca asume "no revocado".
    """

    async def revocar(self, jti: str, expira_en: datetime) -> None: ...

    async def revocar_usuario(self, usuario_id: uuid.UUID, desde: datetime) -> None:
        """Invalida todos los tokens del usuario emitidos hasta `desde` (inclusive, en segundos)."""
        ...

    async def esta_revocado_token(self, jti: str, usuario_id: uuid.UUID, iat: datetime) -> bool:
        """True si el jti fue revocado o si el token se emitió en o antes de revocado-desde."""
        ...
