from pydantic import BaseModel

from app.domain.value_objects.geo import Coordenada


class CoordenadaRespuesta(BaseModel):
    lat: float
    lon: float

    @classmethod
    def desde(cls, coordenada: Coordenada) -> "CoordenadaRespuesta":
        return cls(lat=coordenada.lat, lon=coordenada.lon)
