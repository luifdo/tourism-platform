import json
import logging
from datetime import timedelta
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.domain.conversacion import Conversacion, Mensaje, Rol

logger = logging.getLogger(__name__)

PREFIJO = "recommendation:conversacion:"
TTL_SESION = timedelta(hours=24)
_FALLAS_DE_CONEXION = (RedisConnectionError, RedisTimeoutError, ConnectionError, TimeoutError)


def crear_cliente_valkey(valkey_url: str) -> Redis:
    # Timeouts cortos: si Valkey no responde, el chat y /health deben enterarse rápido.
    return Redis.from_url(valkey_url, socket_connect_timeout=2, socket_timeout=2)


class SondaValkey:
    """Implementa Sonda con un PING a Valkey."""

    def __init__(self, cliente: Redis) -> None:
        self._cliente = cliente

    async def ping(self) -> bool:
        try:
            return bool(await self._cliente.ping())
        except _FALLAS_DE_CONEXION:
            logger.warning("Valkey no responde", exc_info=True)
            return False


class SesionesValkey:
    """Implementa RepositorioSesiones. Cada guardado renueva el TTL de 24 horas."""

    def __init__(self, cliente: Redis, ttl: timedelta = TTL_SESION) -> None:
        self._cliente = cliente
        self._ttl = ttl

    async def obtener(self, conversacion_id: UUID) -> Conversacion | None:
        datos = await self._cliente.get(_llave(conversacion_id))
        if datos is None:
            return None
        return _deserializar(conversacion_id, datos)

    async def guardar(self, conversacion: Conversacion) -> None:
        await self._cliente.set(_llave(conversacion.id), _serializar(conversacion), ex=self._ttl)


def _llave(conversacion_id: UUID) -> str:
    return PREFIJO + str(conversacion_id)


def _serializar(conversacion: Conversacion) -> str:
    return json.dumps(
        {
            "turista_id": str(conversacion.turista_id),
            "mensajes": [{"rol": m.rol.value, "texto": m.texto} for m in conversacion.mensajes],
        },
        ensure_ascii=False,
    )


def _deserializar(conversacion_id: UUID, datos: bytes | str) -> Conversacion:
    contenido = json.loads(datos)
    return Conversacion(
        id=conversacion_id,
        turista_id=UUID(contenido["turista_id"]),
        mensajes=[Mensaje(rol=Rol(m["rol"]), texto=m["texto"]) for m in contenido["mensajes"]],
    )
