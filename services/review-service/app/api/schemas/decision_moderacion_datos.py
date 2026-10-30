from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.decision_moderacion import DecisionModeracion


class DecisionModeracionDatos(BaseModel):
    """Cuerpo de `POST /resenas/{id}/moderacion` (contrato `DecisionModeracion`).

    `motivo` es obligatorio con `OCULTAR` (lo revisa el dominio) y queda en la auditoría.
    """

    model_config = ConfigDict(extra="forbid")

    decision: DecisionModeracion
    motivo: str | None = Field(default=None, min_length=1, max_length=500)
