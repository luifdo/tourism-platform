from dataclasses import dataclass
from datetime import date, datetime

from app.application.dto.cargas_de_zona import CargasDeZona


@dataclass(frozen=True, slots=True)
class CargasCapacidad:
    """Personas en reservas activas y capacidad de cada servicio, agrupados por zona activa.

    `leido_en` es cuándo se leyeron de la base (sale como `calculado_en`): con la caché de
    5 minutos, la Entidad sabe qué tan reciente es el dato.
    """

    fecha: date
    zonas: tuple[CargasDeZona, ...]
    leido_en: datetime
