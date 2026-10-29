from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.application.ports.consulta_mapa import ConsultaMapa
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.geo import Bbox


class VerAlertasEnMapa:
    """UC16 y UC26: alertas vigentes sobre el mapa; nunca se cachean."""

    def __init__(self, consulta: ConsultaMapa, reloj: Reloj) -> None:
        self._consulta = consulta
        self._reloj = reloj

    async def execute(self, vista: Bbox | None) -> list[AlertaEnMapa]:
        return await self._consulta.alertas(self._reloj.ahora(), vista)
