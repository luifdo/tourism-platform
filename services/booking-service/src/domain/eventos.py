"""Evento de dominio: "qué pasó", sin decidir a quién se le avisa ni cómo se envía."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventoDominio:
    tipo: str  # routing key, p. ej. "reserva.confirmada"
    payload: dict[str, Any]
