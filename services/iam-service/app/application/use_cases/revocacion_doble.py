import logging
import uuid
from collections.abc import Callable
from datetime import datetime

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.ports.revocacion_tokens import RevocacionTokens

logger = logging.getLogger(__name__)


class RevocacionDoble:
    """Revoca los tokens de un usuario antes y después del commit (C-21).

    * Antes: si Valkey no responde, ServicioNoDisponibleError y la transacción se deshace.
    * Después: cierra la ventana entre la primera revocación y el commit. Un login en el
      segundo siguiente leía aún los datos viejos y su token quedaba fuera de la marca. Si
      falla, solo queda un log: el cambio ya está confirmado y la primera marca sigue vigente.
    """

    def __init__(self, revocacion: RevocacionTokens, reloj: Callable[[], datetime]) -> None:
        self._revocacion = revocacion
        self._reloj = reloj

    async def antes_del_commit(self, usuario_id: uuid.UUID, desde: datetime) -> None:
        await self._revocacion.revocar_usuario(usuario_id, desde)

    async def despues_del_commit(self, usuario_id: uuid.UUID) -> None:
        try:
            await self._revocacion.revocar_usuario(usuario_id, self._reloj())
        except ServicioNoDisponibleError:
            logger.error(
                "No se pudo repetir la revocación por usuario tras el commit", exc_info=True
            )
