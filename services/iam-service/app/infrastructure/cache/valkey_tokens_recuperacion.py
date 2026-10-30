import hashlib
import logging
import uuid

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.domain.exceptions import ServicioNoDisponibleError
from app.domain.ports.tokens_recuperacion import ESPERA_ENTRE_CORREOS, VALIDEZ_TOKEN

logger = logging.getLogger(__name__)

PREFIJO_TOKEN = "iam:reset:"
PREFIJO_ESPERA = "iam:reset-espera:"
# Hash del token vigente de cada usuario: permite invalidarlo cuando pide otro.
PREFIJO_VIGENTE = "iam:reset-vigente:"
_FALLAS_DE_CONEXION = (RedisConnectionError, RedisTimeoutError, ConnectionError, TimeoutError)


def _huella(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ValkeyTokensRecuperacion:
    """Implementa TokensRecuperacion en Valkey (C-28)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def reservar_envio(self, usuario_id: uuid.UUID) -> bool:
        try:
            # NX: de dos solicitudes simultáneas, solo una envía el correo.
            reservado = await self._client.set(
                PREFIJO_ESPERA + str(usuario_id),
                "1",
                nx=True,
                ex=int(ESPERA_ENTRE_CORREOS.total_seconds()),
            )
        except _FALLAS_DE_CONEXION as exc:
            raise self._no_disponible() from exc
        return bool(reservado)

    async def guardar(self, token: str, usuario_id: uuid.UUID) -> None:
        validez = int(VALIDEZ_TOKEN.total_seconds())
        llave_vigente = PREFIJO_VIGENTE + str(usuario_id)
        huella = _huella(token)
        try:
            anterior = await self._client.get(llave_vigente)
            async with self._client.pipeline(transaction=True) as tx:
                if anterior is not None:
                    tx.delete(PREFIJO_TOKEN + anterior.decode())
                tx.set(PREFIJO_TOKEN + huella, str(usuario_id), ex=validez)
                tx.set(llave_vigente, huella, ex=validez)
                await tx.execute()
        except _FALLAS_DE_CONEXION as exc:
            raise self._no_disponible() from exc

    async def consumir(self, token: str) -> uuid.UUID | None:
        try:
            # GETDEL: de dos peticiones con el mismo enlace, solo una recibe el usuario.
            valor = await self._client.getdel(PREFIJO_TOKEN + _huella(token))
        except _FALLAS_DE_CONEXION as exc:
            raise self._no_disponible() from exc
        return uuid.UUID(valor.decode()) if valor is not None else None

    async def descartar(self, usuario_id: uuid.UUID) -> None:
        llave_vigente = PREFIJO_VIGENTE + str(usuario_id)
        try:
            vigente = await self._client.get(llave_vigente)
            llaves = [llave_vigente, PREFIJO_ESPERA + str(usuario_id)]
            if vigente is not None:
                llaves.append(PREFIJO_TOKEN + vigente.decode())
            await self._client.delete(*llaves)
        except _FALLAS_DE_CONEXION as exc:
            raise self._no_disponible() from exc

    @staticmethod
    def _no_disponible() -> ServicioNoDisponibleError:
        logger.warning("Valkey no responde al usar los tokens de recuperación")
        return ServicioNoDisponibleError()
