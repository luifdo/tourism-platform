from dataclasses import dataclass

from app.application.dto.capacidad_zona import CapacidadZona
from app.application.dto.punto_demanda import PuntoDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.zona_demandada import ZonaDemandada


@dataclass(frozen=True, slots=True)
class Tablero:
    """Tablero de planificación de la Entidad (UC25): reúne UC23 y UC24."""

    rango: RangoFechas
    totales: PuntoDemanda
    capacidad_hoy: tuple[CapacidadZona, ...]
    zonas_mas_demandadas: tuple[ZonaDemandada, ...]
    alertas_vigentes: int
