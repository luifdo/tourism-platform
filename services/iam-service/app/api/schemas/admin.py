import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.enums import Idioma, ResultadoAuditoria, Rol

RolTexto = Literal["Turista", "Prestador", "Entidad", "Admin"]
ResultadoTexto = Literal["Exito", "Denegado", "Error"]
# Tope de lo que se acepta; a la bitácora llegan 500 caracteres como máximo (C-41).
MOTIVO_MAX_ENTRADA = 2000


class UsuarioAdminResponse(BaseModel):
    """Cuenta vista por el Admin (UC27). Nunca incluye la contraseña ni su hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre_completo: str
    rol: Rol
    activo: bool
    email_verificado: bool
    idioma: Idioma
    creado_en: datetime
    actualizado_en: datetime


class PaginaUsuariosResponse(BaseModel):
    items: list[UsuarioAdminResponse]
    total: int
    pagina: int
    tamano: int


class CambioRolRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"rol": "Entidad", "motivo": "Funcionario de la Alcaldía"}]}
    )

    rol: RolTexto
    motivo: str | None = Field(default=None, max_length=MOTIVO_MAX_ENTRADA)


class CambioEstadoRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"activo": False, "motivo": "RNT vencido"}]}
    )

    activo: bool
    motivo: str | None = Field(default=None, max_length=MOTIVO_MAX_ENTRADA)


class EntradaBitacoraResponse(BaseModel):
    """Una fila de la bitácora (UC33). `event_id` solo existe en las de otros servicios."""

    model_config = ConfigDict(from_attributes=True)

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


class PaginaBitacoraResponse(BaseModel):
    items: list[EntradaBitacoraResponse]
    total: int
    pagina: int
    tamano: int
