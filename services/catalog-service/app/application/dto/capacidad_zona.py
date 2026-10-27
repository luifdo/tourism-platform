from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.application.dto.servicio_con_bandera import ServicioConBandera
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.services.calculadora_saturacion import ResultadoSaturacion


@dataclass(frozen=True, slots=True)
class CapacidadZona:
    """Presión sobre la capacidad de carga de una zona en un día (UC24)."""

    zona_id: UUID
    zona: ZonaResumen
    fecha: date
    saturacion: ResultadoSaturacion
    servicios_con_bandera: tuple[ServicioConBandera, ...]
    calculado_en: datetime
