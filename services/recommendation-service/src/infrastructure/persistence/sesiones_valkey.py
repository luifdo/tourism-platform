import json
import logging
from datetime import timedelta
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.application.ports.errores import DependenciaNoDisponibleError
from src.domain.conversacion import Conversacion, Mensaje, Rol

logger = logging.getLogger(__name__)

PREFIJO = "recommendation:conversacion:"
PREFIJO_LIMITE = "recommendation:limite:"
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
        try:
            datos = await self._cliente.get(_llave(conversacion_id))
        except _FALLAS_DE_CONEXION as exc:
            raise _no_disponible("leer la sesión") from exc
        if datos is None:
            return None
        return _deserializar(conversacion_id, datos)

    async def guardar(self, conversacion: Conversacion) -> None:
        try:
            await self._cliente.set(
                _llave(conversacion.id), _serializar(conversacion), ex=self._ttl
            )
        except _FALLAS_DE_CONEXION as exc:
            raise _no_disponible("guardar la sesión") from exc


class LimiteValkey:
    """Implementa LimiteDeTasa con un contador por turista que vence con la ventana."""

    def __init__(self, cliente: Redis, maximo: int, ventana: timedelta) -> None:
        self._cliente = cliente
        self._maximo = maximo
        self._ventana = ventana

    async def permitir(self, turista_id: UUID) -> bool:
        llave = PREFIJO_LIMITE + str(turista_id)
        try:
            async with self._cliente.pipeline(transaction=True) as pipe:
                # El plazo empieza con el primer mensaje de la ventana (NX: no se renueva).
                cuenta, _ = await pipe.incr(llave).expire(llave, self._ventana, nx=True).execute()
        except _FALLAS_DE_CONEXION as exc:
            raise _no_disponible("contar el mensaje") from exc
        return cuenta <= self._maximo


def _no_disponible(accion: str) -> DependenciaNoDisponibleError:
    logger.warning("Valkey no responde al %s", accion)
    return DependenciaNoDisponibleError(f"Valkey no responde al {accion}")


def _llave(conversacion_id: UUID) -> str:
    return PREFIJO + str(conversacion_id)


def _serializar(conversacion: Conversacion) -> str:
    return json.dumps(
        {
            "turista_id": str(conversacion.turista_id),
            "mensajes": [{"rol": m.rol.value, "texto": m.texto} for m in conversacion.mensajes],
            "servicios_vistos": sorted(str(s) for s in conversacion.servicios_vistos),
        },
        ensure_ascii=False,
    )


def _deserializar(conversacion_id: UUID, datos: bytes | str) -> Conversacion:
    contenido = json.loads(datos)
    return Conversacion(
        id=conversacion_id,
        turista_id=UUID(contenido["turista_id"]),
        mensajes=[Mensaje(rol=Rol(m["rol"]), texto=m["texto"]) for m in contenido["mensajes"]],
        # Las sesiones guardadas antes de la Fase 4 no traen el campo.
        servicios_vistos={UUID(s) for s in contenido.get("servicios_vistos", [])},
    )
