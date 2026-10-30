from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class IntencionesZonaDia:
    """Intenciones de visita de los servicios de una zona en un día."""

    zona: str
    fecha: date
    intenciones: int
