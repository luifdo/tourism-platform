"""Caché de búsqueda en Valkey como decorador de ConsultaServicios.

* Clave: `catalog:buscar:{generación}:{idioma}:{hash de los criterios}` (ver CacheVersionada).
* Una entrada que ya no se puede leer (p. ej. guardada antes de un despliegue que cambió
  el resumen) cuenta como fallo de caché.
* Una búsqueda con `fecha` no se cachea: los cupos cambian con cada reserva.
* El detalle de un servicio no se cachea: lleva alertas vigentes que deben verse al instante.
"""

import hashlib
import logging
from datetime import datetime
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from valkey.asyncio import Valkey

from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.dto.servicio_detalle import ServicioDetalle
from app.application.ports.consulta_servicios import ConsultaServicios
from app.infrastructure.cache.cache_versionada import CacheVersionada

logger = logging.getLogger(__name__)

_criterios_json = TypeAdapter(CriteriosBusqueda)
_pagina_json = TypeAdapter(PaginaServicios)


class ConsultaServiciosEnCache:
    def __init__(self, origen: ConsultaServicios, valkey: Valkey) -> None:
        self._origen = origen
        self._cache = CacheVersionada(valkey)

    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        if criterios.filtros.fecha is not None:
            return await self._origen.buscar(criterios)
        huella = hashlib.sha256(_criterios_json.dump_json(criterios)).hexdigest()[:32]
        clave = await self._cache.clave("buscar", criterios.idioma.value, huella)
        if clave is not None:
            guardado = await self._cache.leer(clave)
            if guardado is not None:
                try:
                    return _pagina_json.validate_json(guardado)
                except ValidationError:
                    logger.warning("Entrada de caché ilegible; se consulta PostGIS")
        pagina = await self._origen.buscar(criterios)
        if clave is not None:
            await self._cache.escribir(clave, _pagina_json.dump_json(pagina))
        return pagina

    async def detalle(self, servicio_id: UUID, ahora: datetime) -> ServicioDetalle | None:
        return await self._origen.detalle(servicio_id, ahora)

    async def invalidar(self) -> None:
        """Se llama después de confirmar un cambio del catálogo (servicio, zona, perfil)."""
        await self._cache.invalidar()
