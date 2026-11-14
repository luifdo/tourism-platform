"""Una llamada por segundo entre todas las réplicas, con un turno en Valkey.

`SET clave NX PX 1000` solo lo gana una réplica por segundo; las demás esperan lo que falta
(`PTTL`) hasta un máximo. Si Valkey no responde, se limita dentro del proceso: con varias
réplicas podría pasar de 1/s por un momento, pero nunca sin límite.
"""

import asyncio
import logging
import time

from valkey.asyncio import Valkey
from valkey.exceptions import ValkeyError

logger = logging.getLogger(__name__)

_FALLAS = (ValkeyError, OSError, TimeoutError)


class LimitadorPorSegundo:
    def __init__(self, valkey: Valkey, clave: str, espera_maxima_s: float = 3.0) -> None:
        self._valkey = valkey
        self._clave = clave
        self._espera_maxima_s = espera_maxima_s
        self._candado_local = asyncio.Lock()
        self._ultimo_local = 0.0

    async def turno(self) -> bool:
        """True cuando se puede llamar; False si la espera superaría el máximo."""
        limite = time.monotonic() + self._espera_maxima_s
        while True:
            try:
                if await self._valkey.set(self._clave, b"1", nx=True, px=1000):
                    return True
                restante_ms = await self._valkey.pttl(self._clave)
            except _FALLAS:
                logger.warning("Valkey no responde; límite de Nominatim local", exc_info=True)
                return await self._turno_local(limite)
            espera = max(restante_ms, 50) / 1000
            if time.monotonic() + espera > limite:
                return False
            await asyncio.sleep(espera)

    async def _turno_local(self, limite: float) -> bool:
        async with self._candado_local:
            espera = self._ultimo_local + 1.0 - time.monotonic()
            if time.monotonic() + max(espera, 0) > limite:
                return False
            if espera > 0:
                await asyncio.sleep(espera)
            self._ultimo_local = time.monotonic()
            return True
