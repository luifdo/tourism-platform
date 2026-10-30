from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditoriaPayload(BaseModel):
    """Payload de `auditoria.registrada.v1` (`contracts/events/auditoria.registrada.v1.json`).

    Estricto como el contrato (`additionalProperties: false`): lo que no lo cumple va a la DLQ.
    `accion` admite hasta 50 caracteres porque es lo que cabe en la columna.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    usuario_id: UUID | None = None
    accion: str = Field(min_length=1, max_length=50)
    resultado: Literal["EXITO", "DENEGADO", "ERROR"]
    ip_origen: str | None = None
    detalles: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ip_origen", mode="before")
    @classmethod
    def _ip_no_nula(cls, valor: Any) -> Any:
        # El contrato la define como string: puede faltar, pero no llegar en null. Que el
        # texto sea una IP válida no es del contrato; eso lo resuelve el caso de uso (C-38).
        if valor is None:
            raise ValueError("ip_origen no puede ser null; se omite si no se conoce")
        return valor
