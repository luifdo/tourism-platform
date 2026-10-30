from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.mapa_servicios import MapaServicios
from app.application.ports.consulta_mapa import ConsultaMapa


class VerServiciosEnMapa:
    """UC16: servicios en la vista del mapa, agrupados con zoom bajo.

    La caché de los grupos es transparente: la aporta el adaptador que se inyecta.
    """

    def __init__(self, consulta: ConsultaMapa) -> None:
        self._consulta = consulta

    async def execute(self, criterios: CriteriosMapaServicios) -> MapaServicios:
        return await self._consulta.servicios(criterios)
