from pydantic import BaseModel

from app.api.i18n.aviso_pagos import es_importante, mensaje_aviso
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.valores import RecomendacionDinero
from app.domain.value_objects.idioma import Idioma


class AvisoPagosRespuesta(BaseModel):
    """Qué dinero llevar, en una frase lista para mostrar o para que la lea el chatbot."""

    importante: bool
    recomendacion_dinero: RecomendacionDinero
    mensaje: str

    @classmethod
    def desde(cls, pagos: BloquePagos | None, idioma: Idioma) -> "AvisoPagosRespuesta | None":
        if pagos is None:
            return None
        return cls(
            importante=es_importante(pagos),
            recomendacion_dinero=pagos.recomendacion_dinero,
            mensaje=mensaje_aviso(pagos, idioma),
        )
