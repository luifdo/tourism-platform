from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.application.dto.promedio_aspecto import PromedioAspecto
from app.domain.value_objects.aspecto import Aspecto


@dataclass(frozen=True, slots=True)
class ResumenServicio:
    """Calificación de un servicio: cuentan las reseñas publicadas y en revisión, no las
    ocultas (igual que el promedio de catalog)."""

    servicio_id: UUID
    total: int
    promedio: Decimal | None  # dos decimales; None sin reseñas
    distribucion: dict[int, int]  # puntuación 1–5 → cuántas
    aspectos: dict[Aspecto, PromedioAspecto]
