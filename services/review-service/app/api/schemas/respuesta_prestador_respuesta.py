from datetime import datetime

from pydantic import BaseModel

from app.domain.value_objects.respuesta_prestador import RespuestaPrestador


class RespuestaPrestadorRespuesta(BaseModel):
    """Respuesta pública del prestador (contrato `RespuestaPrestador`)."""

    texto: str
    respondida_en: datetime

    @classmethod
    def desde(cls, respuesta: RespuestaPrestador) -> "RespuestaPrestadorRespuesta":
        return cls(texto=respuesta.texto, respondida_en=respuesta.respondida_en)
