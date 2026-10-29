from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.application.ports.consulta_mapa import ConsultaMapa
from app.domain.value_objects.geo import Bbox


class VerZonasEnMapa:
    """UC16: polígonos de las zonas activas, sin datos de saturación (esos son de la Entidad)."""

    def __init__(self, consulta: ConsultaMapa) -> None:
        self._consulta = consulta

    async def execute(self, vista: Bbox | None, escala: EscalaMapa) -> list[ZonaEnMapa]:
        return await self._consulta.zonas(vista, escala)
