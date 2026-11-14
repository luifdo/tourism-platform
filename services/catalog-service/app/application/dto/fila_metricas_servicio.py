from dataclasses import dataclass
from uuid import UUID

from app.application.dto.reservas_por_estado import ReservasPorEstado
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class FilaMetricasServicio:
    """Lo que la base agrega por servicio; la ocupación la calcula el caso de uso."""

    servicio_id: UUID
    nombre: TextoTraducido
    capacidad_aforo_diario: int
    reservas: ReservasPorEstado
    personas_finalizadas: int
    calificacion_promedio: float | None
    total_resenas: int
    intenciones_visita: int
