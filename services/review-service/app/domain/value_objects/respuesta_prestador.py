from dataclasses import dataclass
from datetime import datetime

from app.domain.errors import DatoInvalido
from app.domain.value_objects.comun import texto_limpio

TEXTO_MAXIMO = 1000


@dataclass(frozen=True)
class RespuestaPrestador:
    """Respuesta pública del prestador dueño del servicio (UC21); una por reseña."""

    texto: str
    respondida_en: datetime

    @classmethod
    def escribir(cls, texto: str, ahora: datetime) -> "RespuestaPrestador":
        limpio = texto_limpio(texto, "texto", TEXTO_MAXIMO)
        if limpio is None:
            raise DatoInvalido(campo="texto", regla="obligatorio")
        return cls(texto=limpio, respondida_en=ahora)
