from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ResenaRecibida:
    """`resena.publicada.v1` (visible) o `resena.ocultada.v1` (no visible), ya validado."""

    event_id: UUID
    ocurrido_en: datetime
    resena_id: UUID
    servicio_id: UUID
    puntuacion: int
    visible: bool
