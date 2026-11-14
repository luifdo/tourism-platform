"""Puerto de lectura del mapa (UC16). Todo recortado a la vista y en coordenadas WGS 84."""

from datetime import datetime
from typing import Protocol

from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.mapa_servicios import MapaServicios
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.domain.value_objects.geo import Bbox


class ConsultaMapa(Protocol):
    async def servicios(self, criterios: CriteriosMapaServicios) -> MapaServicios:
        """Servicios activos en la vista; agrupados si `criterios.escala.agrupa`."""
        ...

    async def zonas(self, vista: Bbox | None, escala: EscalaMapa) -> list[ZonaEnMapa]:
        """Zonas activas que tocan la vista, simplificadas con `escala.tolerancia_grados`."""
        ...

    async def alertas(self, ahora: datetime, vista: Bbox | None) -> list[AlertaEnMapa]:
        """Alertas vigentes que tocan la vista, de mayor a menor nivel."""
        ...
