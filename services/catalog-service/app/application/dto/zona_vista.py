from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class ZonaVista:
    """Zona activa para filtros y mapas; `centro` es un punto garantizado dentro del polígono."""

    id: UUID
    codigo: str
    nombre: TextoTraducido
    centro: Coordenada
