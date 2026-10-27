from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PrestadorAprobadoRecibido:
    """`prestador.aprobado.v1` de iam-service, ya validado."""

    event_id: UUID
    ocurrido_en: datetime
    prestador_id: UUID
    usuario_id: UUID
    razon_social: str | None
