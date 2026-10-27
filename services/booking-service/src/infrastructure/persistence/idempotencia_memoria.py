"""Idempotencia en memoria, para las pruebas y el modo demo (en modo postgres va en Valkey).

Solo sirve con una réplica: cada proceso tiene su propio diccionario.
"""

import time

from application.ports import RespuestaGuardada

TTL_SEGUNDOS = 48 * 3600
TTL_EN_PROCESO = 60  # si el proceso muere a medias, la clave se libera sola


class AlmacenIdempotenciaMemoria:
    def __init__(self, ttl: int = TTL_SEGUNDOS, ttl_en_proceso: int = TTL_EN_PROCESO) -> None:
        self._ttl = ttl
        self._ttl_en_proceso = ttl_en_proceso
        # clave → (vence, respuesta o None mientras está en proceso)
        self._datos: dict[str, tuple[float, RespuestaGuardada | None]] = {}

    def _vigente(self, clave: str) -> tuple[float, RespuestaGuardada | None] | None:
        guardado = self._datos.get(clave)
        if guardado is not None and guardado[0] < time.monotonic():
            del self._datos[clave]
            return None
        return guardado

    async def reservar(self, clave: str) -> bool:
        # Sin await entre la consulta y la escritura: en asyncio nadie más corre en medio.
        if self._vigente(clave) is not None:
            return False
        self._datos[clave] = (time.monotonic() + self._ttl_en_proceso, None)
        return True

    async def obtener(self, clave: str) -> RespuestaGuardada | None:
        guardado = self._vigente(clave)
        return guardado[1] if guardado else None

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None:
        self._datos[clave] = (time.monotonic() + self._ttl, respuesta)

    async def liberar(self, clave: str) -> None:
        self._datos.pop(clave, None)
