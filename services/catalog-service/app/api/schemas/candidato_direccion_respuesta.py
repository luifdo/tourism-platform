from pydantic import BaseModel

from app.application.dto.candidato_direccion import CandidatoDireccion


class CandidatoDireccionRespuesta(BaseModel):
    lat: float
    lon: float
    etiqueta: str

    @classmethod
    def desde(cls, candidato: CandidatoDireccion) -> "CandidatoDireccionRespuesta":
        return cls(
            lat=candidato.ubicacion.lat, lon=candidato.ubicacion.lon, etiqueta=candidato.etiqueta
        )
