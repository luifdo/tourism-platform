from pydantic import BaseModel

from app.application.dto.zona_resumen import ZonaResumen
from app.domain.value_objects.idioma import Idioma


class ZonaResumenRespuesta(BaseModel):
    codigo: str
    nombre: str

    @classmethod
    def desde(cls, zona: ZonaResumen | None, idioma: Idioma) -> "ZonaResumenRespuesta | None":
        if zona is None:
            return None
        return cls(codigo=zona.codigo, nombre=zona.nombre.en_idioma(idioma)[0])
