import hashlib
import logging
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.value_objects.sesion import (
    ResultadoRotacion,
    RotacionInvalida,
    RotacionOk,
    RotacionReutilizada,
    RotacionRevocada,
    SesionCreada,
)
from app.infrastructure.cache.valkey_revocacion import PREFIJO_SESION

logger = logging.getLogger(__name__)

PREFIJO_TOKEN = "iam:refresh:"
PREFIJO_FAMILIA = "iam:refresh-familia:"
# RedisError y no solo los de conexión: un OOM o un READONLY tampoco permiten asumir nada.
_FALLAS = (RedisError, ConnectionError, TimeoutError)

# Las llaves de la familia, de revocado-desde y de sesion-revocada se calculan dentro del script
# porque dependen del registro del token: no funciona con Valkey Cluster (C-60). Los prefijos
# coinciden con PREFIJO_FAMILIA, PREFIJO_USUARIO y PREFIJO_SESION; lo comprueba la integración.
#
# KEYS[1] = token presentado, KEYS[2] = token nuevo.
# ARGV: [1] hash presentado, [2] hash nuevo, [3] ahora en segundos, [4] TTL del refresh,
#       [5] TTL de sesion-revocada.
_ROTAR = """
local t = redis.call('HMGET', KEYS[1], 'familia', 'usuario_id', 'estado')
if not t[1] then return {'invalido'} end
local familia, usuario, estado = t[1], t[2], t[3]
local lf = 'iam:refresh-familia:' .. familia
local f = redis.call('HMGET', lf, 'actual', 'revocada', 'renovado_en')
if not f[1] then return {'invalido'} end
if f[2] == '1' then return {'revocado', familia, usuario} end

local function revocar()
  redis.call('HSET', lf, 'revocada', '1')
  redis.call('SET', 'iam:sesion-revocada:' .. familia, '1', 'EX', ARGV[5])
end

local desde = redis.call('GET', 'iam:revocado-desde:' .. usuario)
if desde and tonumber(f[3]) <= tonumber(desde) then
  revocar()
  return {'revocado', familia, usuario}
end
if estado ~= 'vigente' or f[1] ~= ARGV[1] then
  revocar()
  return {'reutilizado', familia, usuario}
end

redis.call('HSET', KEYS[1], 'estado', 'rotado')
redis.call('HSET', KEYS[2], 'familia', familia, 'usuario_id', usuario, 'estado', 'vigente')
redis.call('EXPIRE', KEYS[2], ARGV[4])
redis.call('HSET', lf, 'actual', ARGV[2], 'renovado_en', ARGV[3])
redis.call('EXPIRE', lf, ARGV[4])
return {'ok', familia, usuario}
"""

# KEYS[1] = familia, KEYS[2] = sesion-revocada. ARGV[1] = TTL de sesion-revocada.
# Un HSET sobre una familia vencida crearía una llave sin TTL. La marca se escribe siempre: tiene
# TTL y cubre el access token aunque la familia se haya perdido.
_REVOCAR_FAMILIA = """
if redis.call('EXISTS', KEYS[1]) == 1 then
  redis.call('HSET', KEYS[1], 'revocada', '1')
end
redis.call('SET', KEYS[2], '1', 'EX', ARGV[1])
return 1
"""


def _huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ValkeySesionesRenovacion:
    """Implementa SesionesRenovacion en Valkey. En Valkey solo va el SHA-256 de cada token.

    ttl_refresh: segundos que vive cada token y, desde la última rotación, su familia.
    ttl_sesion_revocada: vida de un access token más el margen de verificación.
    """

    def __init__(
        self,
        client: Redis,
        reloj: Callable[[], datetime],
        ttl_refresh: int,
        ttl_sesion_revocada: int,
    ) -> None:
        self._client = client
        self._reloj = reloj
        self._ttl_refresh = ttl_refresh
        self._ttl_sesion_revocada = ttl_sesion_revocada

    async def crear(
        self, usuario_id: uuid.UUID, familia: str, emitido_en: datetime
    ) -> SesionCreada:
        token = secrets.token_urlsafe(32)
        huella = _huella(token)
        llave_token = PREFIJO_TOKEN + huella
        llave_familia = PREFIJO_FAMILIA + familia
        try:
            async with self._client.pipeline(transaction=True) as tx:
                tx.hset(
                    llave_token,
                    mapping={
                        "familia": familia,
                        "usuario_id": str(usuario_id),
                        "estado": "vigente",
                    },
                )
                tx.expire(llave_token, self._ttl_refresh)
                tx.hset(
                    llave_familia,
                    mapping={
                        "usuario_id": str(usuario_id),
                        "actual": huella,
                        "revocada": "0",
                        "renovado_en": str(int(emitido_en.timestamp())),
                    },
                )
                tx.expire(llave_familia, self._ttl_refresh)
                await tx.execute()
        except _FALLAS as exc:
            raise self._no_disponible() from exc
        return SesionCreada(
            refresh_token=token,
            familia=familia,
            expira_en=emitido_en + timedelta(seconds=self._ttl_refresh),
            expires_in=self._ttl_refresh,
        )

    async def rotar(self, refresh_token: str) -> ResultadoRotacion:
        nuevo = secrets.token_urlsafe(32)
        presentada, nueva = _huella(refresh_token), _huella(nuevo)
        script = self._client.register_script(_ROTAR)
        try:
            respuesta = await script(
                keys=[PREFIJO_TOKEN + presentada, PREFIJO_TOKEN + nueva],
                args=[
                    presentada,
                    nueva,
                    # El mismo reloj que escribe revocado-desde: la regla compara esos segundos.
                    int(self._reloj().timestamp()),
                    self._ttl_refresh,
                    self._ttl_sesion_revocada,
                ],
            )
        except _FALLAS as exc:
            raise self._no_disponible() from exc

        estado = respuesta[0].decode()
        if estado == "invalido":
            return RotacionInvalida()
        familia, usuario_id = respuesta[1].decode(), uuid.UUID(respuesta[2].decode())
        if estado == "ok":
            return RotacionOk(
                nuevo_token=nuevo,
                familia=familia,
                usuario_id=usuario_id,
                expires_in=self._ttl_refresh,
            )
        if estado == "revocado":
            return RotacionRevocada(familia=familia, usuario_id=usuario_id)
        return RotacionReutilizada(familia=familia, usuario_id=usuario_id)

    async def revocar_familia(self, familia: str) -> None:
        script = self._client.register_script(_REVOCAR_FAMILIA)
        try:
            await script(
                keys=[PREFIJO_FAMILIA + familia, PREFIJO_SESION + familia],
                args=[self._ttl_sesion_revocada],
            )
        except _FALLAS as exc:
            raise self._no_disponible() from exc

    @staticmethod
    def _no_disponible() -> ServicioNoDisponibleError:
        logger.warning("Valkey no responde al usar las sesiones de renovación")
        return ServicioNoDisponibleError()
