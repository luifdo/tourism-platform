from dataclasses import dataclass
from uuid import UUID

from app.application.dto.reservas_por_estado import ReservasPorEstado
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class MetricasServicio:
    """Rendimiento de una oferta del prestador en un rango (UC22), por fecha de la visita.

    `ocupacion` = personas atendidas ÷ (aforo diario × días): puede pasar de 1, porque el
    aforo es la capacidad recomendada, no un tope. La calificación es la de siempre.
    """

    servicio_id: UUID
    nombre: TextoTraducido
    reservas: ReservasPorEstado
    personas_finalizadas: int
    ocupacion: float
    calificacion_promedio: float | None
    total_resenas: int
    intenciones_visita: int
