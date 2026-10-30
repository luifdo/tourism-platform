from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ServicioPendiente:
    """Servicio que el turista visitó y todavía no reseñó."""

    servicio_id: UUID
    ultima_visita: date
