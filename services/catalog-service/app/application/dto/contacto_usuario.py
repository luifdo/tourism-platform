from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.idioma import Idioma


@dataclass(frozen=True, slots=True)
class ContactoUsuario:
    """Datos de contacto que entrega iam al momento de enviar un correo; no se guardan."""

    usuario_id: UUID
    nombre: str
    email: str
    idioma: Idioma = Idioma.ES
