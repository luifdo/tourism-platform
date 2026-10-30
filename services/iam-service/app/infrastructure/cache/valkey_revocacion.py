import logging
import math
import uuid
from collections.abc import Callable
from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.domain.exceptions import ServicioNoDisponibleError

logger = logging.getLogger(__name__)

PREFIJO = "iam:revoked:"
PREFIJO_USUARIO = "iam:revocado-desde:"
_FALLAS_DE_CONEXION = (RedisConnectionError, RedisTimeoutError, ConnectionError, TimeoutError)


def build_valkey_client(valkey_url: str) -> Redis:
    # Timeouts cortos: si Valkey no responde, el logout debe fallar rápido con 503.
    return Redis.from_url(valkey_url, socket_connect_timeout=2, socket_timeout=2)


class ValkeyRevocacionTokens:
    """Implementa RevocacionTokens en Valkey. Falla cerrado: sin respuesta, no hay "no revocado".

    ttl_revocado_desde: segundos que vive "revocado-desde"; basta con la vida máxima de un
    token (TTL + leeway), porque después ya no queda ninguno emitido antes del cambio.
    """

    def __init__(
        self, client: Redis, reloj: Callable[[], datetime], ttl_revocado_desde: int
    ) -> None:
        self._client = client
        self._reloj = reloj
        self._ttl_revocado_desde = ttl_revocado_desde

    async def revocar(self, jti: str, expira_en: datetime) -> None:
        # La llave vive lo mismo que el token: después de exp ya no hace falta recordarla.
        ttl = max(1, math.ceil((expira_en - self._reloj()).total_seconds()))
        try:
            await self._client.set(PREFIJO + jti, "1", ex=ttl)
        except _FALLAS_DE_CONEXION as exc:
            logger.warning("Valkey no responde al revocar el jti %s…", jti[:8])
            raise ServicioNoDisponibleError() from exc

    async def revocar_usuario(self, usuario_id: uuid.UUID, desde: datetime) -> None:
        # Segundos enteros, como el iat de los tokens.
        try:
            await self._client.set(
                PREFIJO_USUARIO + str(usuario_id),
                int(desde.timestamp()),
                ex=self._ttl_revocado_desde,
            )
        except _FALLAS_DE_CONEXION as exc:
            logger.warning("Valkey no responde al revocar los tokens del usuario %s", usuario_id)
            raise ServicioNoDisponibleError() from exc

    async def esta_revocado_token(self, jti: str, usuario_id: uuid.UUID, iat: datetime) -> bool:
        # Una sola ida a Valkey para las dos llaves.
        try:
            por_jti, desde = await self._client.mget(
                PREFIJO + jti, PREFIJO_USUARIO + str(usuario_id)
            )
        except _FALLAS_DE_CONEXION as exc:
            logger.warning("Valkey no responde al consultar el jti %s…", jti[:8])
            raise ServicioNoDisponibleError() from exc
        if por_jti is not None:
            return True
        # <= : un token emitido en el mismo segundo del cambio también queda revocado.
        return desde is not None and int(iat.timestamp()) <= int(desde)
