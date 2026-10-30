import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class EventoPendiente:
    """Evento del outbox aún no confirmado por RabbitMQ, con su sobre ya armado."""

    event_id: uuid.UUID
    event_type: str
    sobre: dict[str, Any]
    creado_en: datetime
    intentos: int = 0
