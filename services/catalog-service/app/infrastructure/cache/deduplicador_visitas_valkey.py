"""Descarte de intenciones de visita repetidas en Valkey (implementa DeduplicadorVisitas).

* Clave: `catalog:intencion:{fecha}:{servicio}:{hash}`, con TTL de 24 h.
* `hash` = HMAC-SHA256 del IP con una sal que cambia cada día (derivada del secreto y la
  fecha): el IP no se guarda ni se puede recuperar, y el mismo visitante tiene otro hash al
  día siguiente, así no se le puede seguir entre días.
* Si Valkey falla, devuelve None y el caso de uso cuenta igual.
"""

import hashlib
import hmac
import logging
from datetime import date
from uuid import UUID

from valkey.asyncio import Valkey
from valkey.exceptions import ValkeyError

logger = logging.getLogger(__name__)

TTL_SEGUNDOS = 24 * 60 * 60
_FALLAS = (ValkeyError, OSError, TimeoutError)


class DeduplicadorVisitasValkey:
    def __init__(self, valkey: Valkey, secreto: str) -> None:
        self._valkey = valkey
        self._secreto = secreto.encode("utf-8")

    def _clave(self, ip: str, servicio_id: UUID, fecha: date) -> str:
        sal = hmac.new(self._secreto, fecha.isoformat().encode(), hashlib.sha256).digest()
        huella = hmac.new(sal, ip.encode(), hashlib.sha256).hexdigest()[:32]
        return f"catalog:intencion:{fecha.isoformat()}:{servicio_id}:{huella}"

    async def primera_vez(self, ip: str, servicio_id: UUID, fecha: date) -> bool | None:
        try:
            nueva = await self._valkey.set(
                self._clave(ip, servicio_id, fecha), b"1", nx=True, ex=TTL_SEGUNDOS
            )
        except _FALLAS:
            logger.warning("Valkey no responde; intención de visita sin descarte", exc_info=True)
            return None
        return bool(nueva)

    async def olvidar(self, ip: str, servicio_id: UUID, fecha: date) -> None:
        try:
            await self._valkey.delete(self._clave(ip, servicio_id, fecha))
        except _FALLAS:
            logger.warning("No se pudo borrar la marca de intención de visita", exc_info=True)
