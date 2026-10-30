import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.value_objects.enums import ResultadoAuditoria


@dataclass(frozen=True)
class FiltroBitacora:
    """Consulta de UC33. El rango de fechas es semiabierto: `desde <= fecha < hasta`."""

    usuario_id: uuid.UUID | None = None
    accion: str | None = None
    resultado: ResultadoAuditoria | None = None
    servicio_origen: str | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
    pagina: int = 1
    tamano: int = 20


@dataclass(frozen=True)
class EntradaBitacora:
    """Una fila de `bitacora_auditoria`, tal como se guardó (de solo lectura)."""

    id: uuid.UUID
    fecha: datetime
    usuario_id: uuid.UUID | None
    accion: str
    resultado: ResultadoAuditoria
    servicio_origen: str
    ip_origen: str | None
    detalles: dict[str, Any]
    correlation_id: str | None
    event_id: uuid.UUID | None


@dataclass(frozen=True)
class PaginaBitacora:
    items: list[EntradaBitacora]
    total: int
    pagina: int
    tamano: int
