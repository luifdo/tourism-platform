from dataclasses import dataclass

from app.application.dto.grupo_en_mapa import GrupoEnMapa
from app.application.dto.servicio_en_mapa import ServicioEnMapa


@dataclass(frozen=True, slots=True)
class MapaServicios:
    """Lo que cae en la vista. Un grupo de un solo servicio llega como servicio."""

    servicios: tuple[ServicioEnMapa, ...]
    grupos: tuple[GrupoEnMapa, ...]
