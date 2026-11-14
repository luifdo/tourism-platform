from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict


class SobreEvento(BaseModel):
    """Sobre común de los eventos recibidos (`contracts/events/envelope.v1.json`).

    Se ignoran campos desconocidos: un productor puede agregar campos opcionales sin que
    los consumidores dejen de entenderlo. `occurred_at` debe traer zona horaria (RFC 3339):
    es la fecha que se guarda en la bitácora (C-39).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    event_id: UUID
    event_type: str
    version: int
    occurred_at: AwareDatetime
    producer: str
    correlation_id: str | None = None
    payload: dict[str, Any]
