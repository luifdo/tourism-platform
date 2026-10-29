from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class ZonaEnMapa:
    """Zona con su polígono ya simplificado para el zoom, como geometría GeoJSON."""

    id: UUID
    codigo: str
    nombre: TextoTraducido
    geometria: dict[str, Any]
