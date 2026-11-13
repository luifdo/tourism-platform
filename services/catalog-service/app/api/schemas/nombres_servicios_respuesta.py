from pydantic import BaseModel

from app.api.schemas.nombre_servicio_respuesta import NombreServicioRespuesta
from app.application.dto.nombre_servicio import NombreServicio
from app.domain.value_objects.idioma import Idioma


class NombresServiciosRespuesta(BaseModel):
    items: list[NombreServicioRespuesta]

    @classmethod
    def desde(cls, servicios: list[NombreServicio], idioma: Idioma) -> "NombresServiciosRespuesta":
        return cls(items=[NombreServicioRespuesta.desde(s, idioma) for s in servicios])
