import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.value_objects.enums import Idioma, Rol


class RegistroRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "maria.perez@example.com",
                    "password": "Tayrona2026",
                    "nombre_completo": "María Pérez",
                    "rol": "Turista",
                    "habeas_data_aceptado": True,
                    "es_mayor_de_edad": True,
                    "idioma": "es",
                }
            ]
        }
    )

    email: EmailStr
    password: str
    nombre_completo: str
    rol: Literal["Turista", "Prestador"]
    habeas_data_aceptado: bool
    es_mayor_de_edad: bool
    # Idioma de los correos (C-06). Se edita en PATCH /api/iam/perfil.
    idioma: Literal["es", "en"] = "es"


class LoginRequest(BaseModel):
    # email es str, no EmailStr: un formato inválido debe responder 401 como cualquier
    # credencial incorrecta, no 422.
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "maria.perez@example.com", "password": "Tayrona2026"}]
        }
    )

    email: str
    password: str


class RecuperarRequest(BaseModel):
    # str, no EmailStr: un formato inválido responde el mismo 202 que cualquier otro correo.
    email: str = Field(max_length=320)


class RecuperarResponse(BaseModel):
    detail: str


class RestablecerRequest(BaseModel):
    # Pydantic ignora los campos extra: ResetView.vue también envía "confirmacion".
    token: str = Field(max_length=512)
    password: str


class UsuarioPublicoResponse(BaseModel):
    """Datos públicos de una cuenta. Nunca incluye la contraseña ni su hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre_completo: str
    rol: Rol
    email_verificado: bool
    idioma: Idioma
    creado_en: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    usuario: UsuarioPublicoResponse


class Jwk(BaseModel):
    kty: str
    n: str
    e: str
    kid: str
    use: str
    alg: str


class JwksResponse(BaseModel):
    keys: list[Jwk]
