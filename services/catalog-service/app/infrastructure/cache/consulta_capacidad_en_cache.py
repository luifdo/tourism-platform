"""Caché de 5 minutos de las cargas de capacidad, como decorador de ConsultaCapacidad.

* Clave: `catalog:capacidad:{generación}:{fecha}:{zona o "todas"}` (ver CacheVersionada).
* Lo cacheado lleva `leido_en`: la respuesta muestra de cuándo es el dato (`calculado_en`).
* Si Valkey falla, se lee la base: la caché nunca tumba una lectura.
"""

import logging
from datetime import date

from pydantic import TypeAdapter, ValidationError
from valkey.asyncio import Valkey

from app.application.dto.cargas_capacidad import CargasCapacidad
from app.application.ports.consulta_capacidad import ConsultaCapacidad
from app.infrastructure.cache.cache_versionada import CacheVersionada

logger = logging.getLogger(__name__)

_cargas_json = TypeAdapter(CargasCapacidad)


class ConsultaCapacidadEnCache:
    def __init__(self, origen: ConsultaCapacidad, valkey: Valkey) -> None:
        self._origen = origen
        self._cache = CacheVersionada(valkey)

    async def cargas(self, fecha: date, zona: str | None = None) -> CargasCapacidad:
        clave = await self._cache.clave("capacidad", fecha.isoformat(), zona or "todas")
        if clave is not None:
            guardado = await self._cache.leer(clave)
            if guardado is not None:
                try:
                    return _cargas_json.validate_json(guardado)
                except ValidationError:
                    logger.warning("Entrada de caché ilegible; se consulta PostGIS")
        cargas = await self._origen.cargas(fecha, zona)
        if clave is not None:
            await self._cache.escribir(clave, _cargas_json.dump_json(cargas))
        return cargas
