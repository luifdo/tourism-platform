"""Idempotencia en Valkey (Guía §6.3), compartida por todas las réplicas de la API.

Cada clave `idem:booking:{usuario}:{método}:{ruta}:{Idempotency-Key}` guarda uno de dos valores:

* `EN_PROCESO`, puesto con `SET NX EX 60` por la primera petición. NX hace la reserva atómica:
  de dos peticiones simultáneas solo una la consigue. Los 60 s liberan la clave si el pod muere
  a medias.
* La respuesta en JSON (`estado`, `cuerpo` en base64, `headers`), con `SET EX` de 48 h.

Valkey habla el protocolo de Redis, así que se usa el cliente `redis` (asyncio).
"""

import base64
import json
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from application.errores import IdempotenciaNoDisponible
from application.ports import RespuestaGuardada

TTL_SEGUNDOS = 48 * 3600
TTL_EN_PROCESO = 60
EN_PROCESO = b"EN_PROCESO"

log = logging.getLogger("booking.idempotencia")


def crear_cliente(url: str) -> Redis:
    """No se conecta todavía: la primera conexión llega con el primer comando."""
    return Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)


class AlmacenIdempotenciaValkey:
    def __init__(self, cliente: Redis, ttl: int = TTL_SEGUNDOS, ttl_en_proceso: int = TTL_EN_PROCESO) -> None:
        self._cliente = cliente
        self._ttl = ttl
        self._ttl_en_proceso = ttl_en_proceso

    async def reservar(self, clave: str) -> bool:
        try:
            return bool(await self._cliente.set(clave, EN_PROCESO, nx=True, ex=self._ttl_en_proceso))
        except RedisError as error:
            raise IdempotenciaNoDisponible("No se pudo verificar la Idempotency-Key; reintente.") from error

    async def obtener(self, clave: str) -> RespuestaGuardada | None:
        try:
            valor = await self._cliente.get(clave)
        except RedisError as error:
            raise IdempotenciaNoDisponible("No se pudo verificar la Idempotency-Key; reintente.") from error
        if valor is None or valor == EN_PROCESO:
            return None
        datos = json.loads(valor)
        return RespuestaGuardada(datos["estado"], base64.b64decode(datos["cuerpo"]), datos["headers"])

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None:
        valor = json.dumps({
            "estado": respuesta.estado,
            "cuerpo": base64.b64encode(respuesta.cuerpo).decode("ascii"),
            "headers": respuesta.headers,
        })
        try:
            await self._cliente.set(clave, valor, ex=self._ttl)
        except RedisError:
            # La operación ya se hizo y se confirmó: se responde igual. Un reintento posterior no
            # encontrará la respuesta, pero las reglas de negocio lo frenan (RESERVA_DUPLICADA al
            # solicitar; DIA_EXISTENTE u omitidos en el calendario). Se deja constancia.
            log.warning("No se guardó en Valkey la respuesta de %s", clave)

    async def liberar(self, clave: str) -> None:
        try:
            await self._cliente.delete(clave)
        except RedisError:
            pass  # la marca vence sola en TTL_EN_PROCESO segundos
