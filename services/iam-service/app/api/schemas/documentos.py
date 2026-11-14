import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.domain.entities.documento_verificacion import EstadoVerificacion
from app.domain.value_objects.enums import EstadoDocumento, TipoDocumento

TipoTexto = Literal["RNT", "RUT"]
EstadoVerificacionTexto = Literal["incompleto", "pendiente", "rechazado", "aprobado"]
Motivo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class DocumentoResponse(BaseModel):
    """Nunca incluye la llave del objeto en SeaweedFS."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo_documento: TipoDocumento
    estado: EstadoDocumento
    vigente: bool
    tipo_contenido: str
    tamano_bytes: int
    motivo_rechazo: str | None
    fecha_subida: datetime
    revisado_en: datetime | None


class DocumentoAdminResponse(DocumentoResponse):
    revisado_por: uuid.UUID | None


class VerificacionResponse(BaseModel):
    usuario_id: uuid.UUID
    razon_social: str | None
    estado: EstadoVerificacion
    documentos: list[DocumentoResponse]


class VerificacionAdminResponse(VerificacionResponse):
    documentos: list[DocumentoAdminResponse]  # type: ignore[assignment]


class ResumenPrestadorResponse(BaseModel):
    usuario_id: uuid.UUID
    nombre_completo: str
    email: str
    activo: bool
    razon_social: str | None
    estado: EstadoVerificacion
    documentos: list[DocumentoAdminResponse]


class PaginaPrestadoresResponse(BaseModel):
    items: list[ResumenPrestadorResponse]
    total: int
    pagina: int
    tamano: int


class EnlaceDocumentoResponse(BaseModel):
    url: str
    expira_en: datetime


class DocumentoRechazadoRequest(BaseModel):
    tipo: TipoTexto
    motivo: Motivo


class RechazoRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"documentos": [{"tipo": "RUT", "motivo": "El RUT está ilegible."}]}]
        }
    )

    documentos: list[DocumentoRechazadoRequest] = Field(min_length=1, max_length=2)

    @field_validator("documentos")
    @classmethod
    def _tipos_distintos(
        cls, documentos: list[DocumentoRechazadoRequest]
    ) -> list[DocumentoRechazadoRequest]:
        if len({d.tipo for d in documentos}) != len(documentos):
            raise ValueError("Cada tipo de documento puede aparecer una sola vez.")
        return documentos
