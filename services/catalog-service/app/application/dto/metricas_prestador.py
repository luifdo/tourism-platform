from dataclasses import dataclass

from app.application.dto.metricas_servicio import MetricasServicio
from app.application.dto.rango_fechas import RangoFechas


@dataclass(frozen=True, slots=True)
class MetricasPrestador:
    rango: RangoFechas
    servicios: tuple[MetricasServicio, ...]
