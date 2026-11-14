from dataclasses import dataclass

from app.domain.value_objects.geo import Coordenada


@dataclass(frozen=True, slots=True)
class GrupoEnMapa:
    """Varios servicios cercanos con zoom bajo; `ubicacion` es el promedio de sus puntos."""

    ubicacion: Coordenada
    conteo: int
