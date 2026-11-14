from app.api.i18n.etiquetas import etiqueta
from app.api.schemas.resena_publica_respuesta import ResenaPublicaRespuesta
from app.domain.entities.resena import Resena
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.idioma import Idioma


class ResenaPropiaRespuesta(ResenaPublicaRespuesta):
    """La reseña vista por su autor (contrato `ResenaPropia`): con su estado y versión."""

    estado: EstadoResena
    estado_etiqueta: str
    version: int

    @classmethod
    def desde(cls, resena: Resena, idioma: Idioma) -> "ResenaPropiaRespuesta":
        return cls(
            **cls.campos(resena, idioma),
            estado=resena.estado,
            estado_etiqueta=etiqueta(resena.estado, idioma),
            version=resena.version,
        )
