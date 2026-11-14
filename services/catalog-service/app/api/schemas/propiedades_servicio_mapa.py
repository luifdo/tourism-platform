from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.application.dto.servicio_en_mapa import ServicioEnMapa
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.idioma import Idioma


class PropiedadesServicioMapa(BaseModel):
    tipo: Literal["servicio"] = "servicio"
    id: UUID
    nombre: str
    categoria: Categoria
    categoria_etiqueta: str
    calificacion_promedio: float | None

    @classmethod
    def desde(cls, servicio: ServicioEnMapa, idioma: Idioma) -> "PropiedadesServicioMapa":
        return cls(
            id=servicio.id,
            nombre=servicio.nombre.en_idioma(idioma)[0],
            categoria=servicio.categoria,
            categoria_etiqueta=etiqueta(servicio.categoria, idioma),
            calificacion_promedio=servicio.calificacion_promedio,
        )
