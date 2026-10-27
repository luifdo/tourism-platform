"""Caché de los grupos del mapa en Valkey como decorador de ConsultaMapa.

* Solo se cachean los grupos (zoom bajo): son la consulta costosa, cambian poco y la vista
  alineada a la cuadrícula hace que vistas cercanas compartan clave. El nombre se guarda en
  ambos idiomas, así que la clave no depende del idioma.
* Con zoom alto la vista es pequeña y rara vez se repite; zonas y alertas no se cachean
  (las alertas deben verse al instante).
* Clave: `catalog:mapa:{generación}:servicios:{hash}`; la generación es compartida con la
  búsqueda, así que un cambio del catálogo invalida ambas.
"""

import hashlib
from datetime import datetime

from pydantic import TypeAdapter
from valkey.asyncio import Valkey

from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.mapa_servicios import MapaServicios
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.application.ports.consulta_mapa import ConsultaMapa
from app.domain.value_objects.geo import Bbox
from app.infrastructure.cache.cache_versionada import CacheVersionada

_criterios_json = TypeAdapter(CriteriosMapaServicios)
_mapa_json = TypeAdapter(MapaServicios)


class ConsultaMapaEnCache:
    def __init__(self, origen: ConsultaMapa, valkey: Valkey) -> None:
        self._origen = origen
        self._cache = CacheVersionada(valkey)

    async def servicios(self, criterios: CriteriosMapaServicios) -> MapaServicios:
        # Con `fecha` tampoco: los cupos cambian con cada reserva.
        if not criterios.escala.agrupa or criterios.filtros.fecha is not None:
            return await self._origen.servicios(criterios)
        huella = hashlib.sha256(_criterios_json.dump_json(criterios)).hexdigest()[:32]
        clave = await self._cache.clave("mapa", "servicios", huella)
        if clave is not None:
            guardado = await self._cache.leer(clave)
            if guardado is not None:
                return _mapa_json.validate_json(guardado)
        mapa = await self._origen.servicios(criterios)
        if clave is not None:
            await self._cache.escribir(clave, _mapa_json.dump_json(mapa))
        return mapa

    async def zonas(self, vista: Bbox | None, escala: EscalaMapa) -> list[ZonaEnMapa]:
        return await self._origen.zonas(vista, escala)

    async def alertas(self, ahora: datetime, vista: Bbox | None) -> list[AlertaEnMapa]:
        return await self._origen.alertas(ahora, vista)
