from uuid import UUID

from pydantic import BaseModel

from app.application.dto.servicio_con_bandera import ServicioConBandera
from app.domain.value_objects.idioma import Idioma


class ServicioConBanderaRespuesta(BaseModel):
    servicio_id: UUID
    nombre: str
    indice: float

    @classmethod
    def desde(cls, servicio: ServicioConBandera, idioma: Idioma) -> "ServicioConBanderaRespuesta":
        return cls(
            servicio_id=servicio.servicio_id,
            nombre=servicio.nombre.en_idioma(idioma)[0],
            indice=servicio.indice,
        )
