import enum
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.domain.value_objects.enums import EstadoDocumento, TipoDocumento

TIPOS_REQUERIDOS = frozenset({TipoDocumento.RNT, TipoDocumento.RUT})


@dataclass(kw_only=True)
class DocumentoVerificacion:
    """RNT o RUT de un prestador (UC37). id y fecha_subida los asigna la persistencia.

    `vigente`: el último cargado de cada tipo; los reemplazados se conservan (C-30).
    """

    usuario_id: uuid.UUID
    tipo_documento: TipoDocumento
    objeto_s3: str
    tipo_contenido: str
    tamano_bytes: int
    estado: EstadoDocumento = EstadoDocumento.PENDIENTE
    vigente: bool = True
    motivo_rechazo: str | None = None
    revisado_por: uuid.UUID | None = None
    revisado_en: datetime | None = None
    id: uuid.UUID | None = None
    fecha_subida: datetime | None = None


class EstadoVerificacion(enum.Enum):
    """Estado del prestador, derivado de sus documentos vigentes (UC28)."""

    INCOMPLETO = "incompleto"  # falta el RNT o el RUT
    PENDIENTE = "pendiente"  # los dos cargados y al menos uno sin revisar
    RECHAZADO = "rechazado"  # al menos uno rechazado: debe cargar otro
    APROBADO = "aprobado"  # los dos aprobados


def estado_verificacion(vigentes: Iterable[DocumentoVerificacion]) -> EstadoVerificacion:
    """Rechazado tiene prioridad: es lo que el prestador debe corregir primero."""
    por_tipo = {d.tipo_documento: d.estado for d in vigentes}
    if EstadoDocumento.RECHAZADO in por_tipo.values():
        return EstadoVerificacion.RECHAZADO
    if set(por_tipo) != TIPOS_REQUERIDOS:
        return EstadoVerificacion.INCOMPLETO
    if all(e is EstadoDocumento.APROBADO for e in por_tipo.values()):
        return EstadoVerificacion.APROBADO
    return EstadoVerificacion.PENDIENTE
