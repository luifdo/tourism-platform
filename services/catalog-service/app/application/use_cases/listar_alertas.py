from uuid import UUID

from app.application.dto.alerta_vista import AlertaVista
from app.application.ports.consulta_alertas import ConsultaAlertas
from app.domain.ports.reloj import Reloj


class ListarAlertas:
    """UC26 (lectura): alertas oficiales vigentes; la usa la tool `alertas_oficiales`."""

    def __init__(self, consulta: ConsultaAlertas, reloj: Reloj) -> None:
        self._consulta = consulta
        self._reloj = reloj

    async def execute(
        self, zona: str | None = None, servicio_id: UUID | None = None
    ) -> list[AlertaVista]:
        return await self._consulta.vigentes(
            self._reloj.ahora(), zona=zona, servicio_id=servicio_id
        )
