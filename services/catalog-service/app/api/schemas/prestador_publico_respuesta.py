from uuid import UUID

from pydantic import BaseModel

from app.application.dto.prestador_publico import PrestadorPublico
from app.domain.value_objects.idioma import Idioma


class PrestadorPublicoRespuesta(BaseModel):
    id: UUID
    razon_social: str | None
    telefono: str | None
    politica_cancelacion: str | None

    @classmethod
    def desde(cls, prestador: PrestadorPublico, idioma: Idioma) -> "PrestadorPublicoRespuesta":
        politica = prestador.politica_cancelacion
        return cls(
            id=prestador.id,
            razon_social=prestador.razon_social,
            telefono=prestador.telefono,
            politica_cancelacion=politica.en_idioma(idioma)[0] if politica else None,
        )
