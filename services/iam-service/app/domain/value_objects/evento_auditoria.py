import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.value_objects.enums import ResultadoAuditoria


@dataclass(frozen=True, kw_only=True)
class EventoAuditoria:
    """Un `auditoria.registrada` de otro servicio, listo para la bitácora (UC33, RNF-10).

    `event_id` es la llave de idempotencia (C-04) y `ocurrido_en` es la fecha del hecho en el
    servicio de origen, no la de inserción (C-39).
    """

    event_id: uuid.UUID
    servicio_origen: str
    ocurrido_en: datetime
    accion: str
    resultado: ResultadoAuditoria
    usuario_id: uuid.UUID | None = None
    ip_origen: str | None = None
    detalles: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
