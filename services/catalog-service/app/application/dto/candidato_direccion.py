from dataclasses import dataclass

from app.domain.value_objects.geo import Coordenada


@dataclass(frozen=True, slots=True)
class CandidatoDireccion:
    """Sugerencia de Nominatim; el prestador confirma el punto en el mapa antes de guardar."""

    ubicacion: Coordenada
    etiqueta: str
