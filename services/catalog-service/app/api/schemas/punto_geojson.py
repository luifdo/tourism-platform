from typing import Literal

from pydantic import BaseModel

from app.domain.value_objects.geo import Coordenada


class PuntoGeoJSON(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]

    @classmethod
    def desde(cls, coordenada: Coordenada) -> "PuntoGeoJSON":
        # RFC 7946: longitud primero. Es el error más común al dibujar en Leaflet.
        return cls(coordinates=(coordenada.lon, coordenada.lat))
