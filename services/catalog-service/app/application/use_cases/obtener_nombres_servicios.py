from collections.abc import Sequence
from uuid import UUID

from app.application.dto.nombre_servicio import NombreServicio
from app.application.ports.consulta_servicios import ConsultaServicios


class ObtenerNombresServicios:
    """Nombres de varios servicios, activos o no (booking-service/INTEGRACION.md §2.6, opción a).

    La PWA los usa en las reservas y reseñas, que solo guardan `servicio_id`. Los ids repetidos
    se consultan una vez; el límite de cantidad lo pone el adaptador HTTP.
    """

    def __init__(self, consulta: ConsultaServicios) -> None:
        self._consulta = consulta

    async def execute(self, ids: Sequence[UUID]) -> list[NombreServicio]:
        return await self._consulta.nombres(list(dict.fromkeys(ids)))
