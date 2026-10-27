from uuid import UUID

from app.application.dto.servicio_detalle import ServicioDetalle
from app.application.ports.consulta_servicios import ConsultaServicios
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj


class ObtenerServicio:
    """UC9: ficha de un servicio activo."""

    def __init__(self, consulta: ConsultaServicios, reloj: Reloj) -> None:
        self._consulta = consulta
        self._reloj = reloj

    async def execute(self, servicio_id: UUID) -> ServicioDetalle:
        detalle = await self._consulta.detalle(servicio_id, self._reloj.ahora())
        if detalle is None:
            raise NoEncontrado(recurso="servicio", id=str(servicio_id))
        return detalle
