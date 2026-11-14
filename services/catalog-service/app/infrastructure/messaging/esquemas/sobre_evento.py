from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SobreEvento(BaseModel):
    """Sobre común de los eventos recibidos (`contracts/events/envelope.v1.json`).

    Se ignoran campos desconocidos: un productor puede agregar campos opcionales sin que
    los consumidores dejen de entenderlo.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    producer: str
    correlation_id: str | None = None
    payload: dict[str, Any]
