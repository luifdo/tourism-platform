from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PuntoDemanda:
    """Personas que vienen (fecha de la visita) en un periodo, por el estado actual de su
    reserva. `canceladas` incluye las rechazadas."""

    periodo: date
    solicitadas: int = 0
    confirmadas: int = 0
    finalizadas: int = 0
    canceladas: int = 0
    zona: str | None = None
