from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.coordenada_respuesta import CoordenadaRespuesta
from app.application.dto.zona_vista import ZonaVista
from app.domain.value_objects.idioma import Idioma


class ZonaRespuesta(BaseModel):
    id: UUID
    codigo: str
    nombre: str
    centro: CoordenadaRespuesta

    @classmethod
    def desde(cls, zona: ZonaVista, idioma: Idioma) -> "ZonaRespuesta":
        return cls(
            id=zona.id,
            codigo=zona.codigo,
            nombre=zona.nombre.en_idioma(idioma)[0],
            centro=CoordenadaRespuesta.desde(zona.centro),
        )
