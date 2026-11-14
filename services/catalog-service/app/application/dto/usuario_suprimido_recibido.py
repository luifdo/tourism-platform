from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UsuarioSuprimidoRecibido:
    """`usuario.suprimido.v1` de iam-service, ya validado."""

    event_id: UUID
    ocurrido_en: datetime
    usuario_id: UUID
