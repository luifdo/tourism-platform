import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Idioma, Rol


class PerfilResponse(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str
    rol: Rol
    idioma: Idioma
    razon_social: str | None
    creado_en: datetime

    @classmethod
    def de(cls, usuario: Usuario) -> "PerfilResponse":
        return cls(
            id=usuario.id,  # type: ignore[arg-type]
            email=usuario.email,
            nombre=usuario.nombre_completo,
            rol=usuario.rol,
            idioma=usuario.idioma,
            razon_social=usuario.razon_social,
            creado_en=usuario.creado_en,  # type: ignore[arg-type]
        )


class EditarPerfilRequest(BaseModel):
    # forbid: enviar `email` o `razon_social` responde 422 en vez de un 200 que no los cambió
    # (C-51).
    model_config = ConfigDict(extra="forbid")

    nombre: str | None = None
    idioma: Literal["es", "en"] | None = None


class CambiarContrasenaRequest(BaseModel):
    password_actual: str
    password_nueva: str


class SuprimirDatosRequest(BaseModel):
    password: str
