from uuid import UUID

from pydantic import BaseModel

from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.domain.value_objects.idioma import Idioma


class PropiedadesZonaMapa(BaseModel):
    id: UUID
    codigo: str
    nombre: str

    @classmethod
    def desde(cls, zona: ZonaEnMapa, idioma: Idioma) -> "PropiedadesZonaMapa":
        return cls(id=zona.id, codigo=zona.codigo, nombre=zona.nombre.en_idioma(idioma)[0])
