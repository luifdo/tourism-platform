from app.application.dto.zona_vista import ZonaVista
from app.application.ports.consulta_zonas import ConsultaZonas


class ListarZonas:
    """Zonas activas para los filtros de la PWA y el parámetro `zona` del chatbot."""

    def __init__(self, consulta: ConsultaZonas) -> None:
        self._consulta = consulta

    async def execute(self) -> list[ZonaVista]:
        return await self._consulta.activas()
