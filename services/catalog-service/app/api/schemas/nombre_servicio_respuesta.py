from uuid import UUID

from pydantic import BaseModel

from app.application.dto.nombre_servicio import NombreServicio
from app.domain.value_objects.idioma import Idioma


class NombreServicioRespuesta(BaseModel):
    id: UUID
    nombre: str
    activo: bool

    @classmethod
    def desde(cls, servicio: NombreServicio, idioma: Idioma) -> "NombreServicioRespuesta":
        return cls(
            id=servicio.id, nombre=servicio.nombre.en_idioma(idioma)[0], activo=servicio.activo
        )
