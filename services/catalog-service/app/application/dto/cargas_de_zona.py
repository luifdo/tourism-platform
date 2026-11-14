from dataclasses import dataclass
from uuid import UUID

from app.application.dto.carga_de_servicio import CargaDeServicio
from app.application.dto.zona_resumen import ZonaResumen


@dataclass(frozen=True, slots=True)
class CargasDeZona:
    zona_id: UUID
    zona: ZonaResumen
    servicios: tuple[CargaDeServicio, ...]
