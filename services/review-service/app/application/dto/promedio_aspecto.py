from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PromedioAspecto:
    """Promedio (dos decimales) de un aspecto y cuántas reseñas lo calificaron."""

    promedio: Decimal
    total: int
