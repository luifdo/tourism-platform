"""Caché en Valkey que se invalida entera incrementando una generación (Plan §6.2, ESC-02).

* Clave: `catalog:{recurso}:{generación}:{partes...}`, TTL de 300 s.
* Invalidación: cada cambio del catálogo incrementa `catalog:gen`; las claves de la
  generación anterior quedan huérfanas y expiran solas (no hace falta SCAN ni borrar). La
  búsqueda y el mapa comparten la generación: un cambio invalida ambos.
* Si Valkey falla o tarda, devuelve None y quien la usa consulta PostGIS: la caché nunca
  tumba una lectura.
"""

import logging

from valkey.asyncio import Valkey
from valkey.exceptions import ValkeyError

logger = logging.getLogger(__name__)

CLAVE_GENERACION = "catalog:gen"
TTL_SEGUNDOS = 300

_FALLAS = (ValkeyError, OSError, TimeoutError)


class CacheVersionada:
    def __init__(self, valkey: Valkey) -> None:
        self._valkey = valkey

    async def clave(self, recurso: str, *partes: str) -> str | None:
        """None si Valkey no responde: la lectura sigue sin caché."""
        try:
            generacion = int(await self._valkey.get(CLAVE_GENERACION) or 0)
        except _FALLAS:
            logger.warning("Valkey no responde; lectura sin caché", exc_info=True)
            return None
        return ":".join(("catalog", recurso, str(generacion), *partes))

    async def leer(self, clave: str) -> bytes | None:
        try:
            return await self._valkey.get(clave)
        except _FALLAS:
            logger.warning("Valkey no responde; lectura sin caché", exc_info=True)
            return None

    async def escribir(self, clave: str, valor: bytes) -> None:
        try:
            await self._valkey.set(clave, valor, ex=TTL_SEGUNDOS)
        except _FALLAS:
            logger.warning("No se pudo guardar en la caché", exc_info=True)

    async def invalidar(self) -> None:
        try:
            await self._valkey.incr(CLAVE_GENERACION)
        except _FALLAS:
            logger.warning("No se pudo invalidar la caché", exc_info=True)
