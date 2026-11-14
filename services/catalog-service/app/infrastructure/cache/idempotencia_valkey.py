"""Idempotencia de formularios en Valkey (Plan §6.8; implementa AlmacenIdempotencia).

* Mientras la operación corre, la clave vale `en_proceso` durante 60 s como máximo (si el
  pod muere a mitad, el reintento puede ejecutarse pasado ese tiempo).
* Al terminar con éxito se guarda la respuesta 48 h (`Idempotency-Key` del contrato).
* Si Valkey no responde, la operación se ejecuta sin protección: el `If-Match` sigue
  evitando dobles ediciones, y solo un POST reenviado justo en esa falla podría duplicarse.
"""

import logging

from pydantic import TypeAdapter
from valkey.asyncio import Valkey
from valkey.exceptions import ValkeyError

from app.application.dto.respuesta_guardada import RespuestaGuardada

logger = logging.getLogger(__name__)

TTL_RESPUESTA_SEGUNDOS = 48 * 3600
TTL_EN_PROCESO_SEGUNDOS = 60
_EN_PROCESO = b"en_proceso"
_FALLAS = (ValkeyError, OSError, TimeoutError)
_respuesta_json = TypeAdapter(RespuestaGuardada)


class IdempotenciaValkey:
    def __init__(self, valkey: Valkey) -> None:
        self._valkey = valkey

    async def reservar(self, clave: str) -> RespuestaGuardada | bool:
        try:
            if await self._valkey.set(clave, _EN_PROCESO, nx=True, ex=TTL_EN_PROCESO_SEGUNDOS):
                return True
            valor = await self._valkey.get(clave)
        except _FALLAS:
            logger.warning("Valkey no responde; operación sin idempotencia", exc_info=True)
            return True
        if valor is None or valor == _EN_PROCESO:
            return False  # el otro intento sigue (o acaba de expirar): que el cliente reintente
        return _respuesta_json.validate_json(valor)

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None:
        try:
            await self._valkey.set(
                clave, _respuesta_json.dump_json(respuesta), ex=TTL_RESPUESTA_SEGUNDOS
            )
        except _FALLAS:
            logger.warning("No se pudo guardar la respuesta idempotente", exc_info=True)

    async def liberar(self, clave: str) -> None:
        try:
            await self._valkey.delete(clave)
        except _FALLAS:
            logger.warning("No se pudo liberar la clave idempotente", exc_info=True)
