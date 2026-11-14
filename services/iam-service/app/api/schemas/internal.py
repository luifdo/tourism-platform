import uuid

from pydantic import BaseModel

from app.domain.value_objects.enums import Idioma


class ContactoUsuarioResponse(BaseModel):
    """`ContactoUsuario` de `contracts/openapi/iam-interno.yaml`."""

    usuario_id: uuid.UUID
    nombre: str
    email: str
    idioma: Idioma
