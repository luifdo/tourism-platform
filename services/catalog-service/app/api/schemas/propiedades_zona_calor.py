from uuid import UUID

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.application.dto.zona_con_saturacion import ZonaConSaturacion
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.saturacion import NivelSaturacion


class PropiedadesZonaCalor(BaseModel):
    """Propiedades de una zona en el mapa de calor; sin servicios no hay índice ni nivel."""

    id: UUID
    codigo: str
    nombre: str
    indice: float | None
    nivel: NivelSaturacion | None
    nivel_etiqueta: str | None

    @classmethod
    def desde(cls, zona: ZonaConSaturacion, idioma: Idioma) -> "PropiedadesZonaCalor":
        s = zona.saturacion
        return cls(
            id=zona.zona.id,
            codigo=zona.zona.codigo,
            nombre=zona.zona.nombre.en_idioma(idioma)[0],
            indice=s.indice if s else None,
            nivel=s.nivel if s else None,
            nivel_etiqueta=etiqueta(s.nivel, idioma) if s else None,
        )
