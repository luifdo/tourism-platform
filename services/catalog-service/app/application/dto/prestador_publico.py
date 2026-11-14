from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class PrestadorPublico:
    """Datos del prestador que se muestran en la ficha de un servicio (UC9)."""

    id: UUID
    razon_social: str | None
    telefono: str | None
    politica_cancelacion: TextoTraducido | None
