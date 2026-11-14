from datetime import date

from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.zona_con_saturacion import ZonaConSaturacion
from app.application.ports.consulta_mapa import ConsultaMapa
from app.application.use_cases.consultar_capacidad import ConsultarCapacidad
from app.domain.value_objects.geo import Bbox
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class VerMapaCalor:
    """RF-07: polígonos de las zonas coloreados por su índice de saturación ese día."""

    def __init__(self, mapa: ConsultaMapa, capacidad: ConsultarCapacidad) -> None:
        self._mapa = mapa
        self._capacidad = capacidad

    async def execute(
        self, identidad: Identidad, fecha: date | None, vista: Bbox | None, escala: EscalaMapa
    ) -> list[ZonaConSaturacion]:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        por_zona = {
            c.zona_id: c.saturacion for c in await self._capacidad.execute(identidad, fecha)
        }
        return [
            ZonaConSaturacion(zona=z, saturacion=por_zona.get(z.id))
            for z in await self._mapa.zonas(vista, escala)
        ]
