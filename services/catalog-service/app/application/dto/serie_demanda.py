from dataclasses import dataclass

from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.punto_demanda import PuntoDemanda


@dataclass(frozen=True, slots=True)
class SerieDemanda:
    agrupacion: AgrupacionDemanda
    serie: tuple[PuntoDemanda, ...]
