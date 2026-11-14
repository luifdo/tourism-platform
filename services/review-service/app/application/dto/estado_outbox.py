from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EstadoOutbox:
    """Para las métricas: cuántos eventos esperan y desde cuándo espera el más viejo."""

    pendientes: int
    mas_antiguo: datetime | None
