from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.api.i18n.etiquetas import AUTOR, etiqueta
from app.api.schemas.aspectos_datos import AspectosDatos
from app.api.schemas.respuesta_prestador_respuesta import RespuestaPrestadorRespuesta
from app.domain.entities.resena import Resena
from app.domain.value_objects.idioma import Idioma


class ResenaPublicaRespuesta(BaseModel):
    """Vista pública y anónima (contrato `ResenaPublica`): nunca el nombre ni el id del
    turista, solo "Turista verificado" y el mes de la visita."""

    id: UUID
    servicio_id: UUID
    autor: str
    mes_visita: str
    puntuacion: int
    aspectos: AspectosDatos
    aspectos_etiquetas: dict[str, str]
    comentario: str | None
    respuesta: RespuestaPrestadorRespuesta | None
    creada_en: datetime
    editada_en: datetime | None

    @classmethod
    def campos(cls, resena: Resena, idioma: Idioma) -> dict[str, Any]:
        """Los campos públicos; las vistas del autor, el prestador y el Admin agregan los suyos."""
        aspectos = resena.contenido.aspectos
        return {
            "id": resena.id,
            "servicio_id": resena.servicio_id,
            "autor": AUTOR[idioma],
            "mes_visita": resena.mes_visita,
            "puntuacion": resena.contenido.puntuacion,
            "aspectos": AspectosDatos.desde(aspectos),
            "aspectos_etiquetas": {a.value: etiqueta(a, idioma) for a in aspectos},
            "comentario": resena.contenido.comentario,
            "respuesta": (
                RespuestaPrestadorRespuesta.desde(resena.respuesta) if resena.respuesta else None
            ),
            "creada_en": resena.creada_en,
            "editada_en": resena.editada_en,
        }

    @classmethod
    def desde(cls, resena: Resena, idioma: Idioma) -> "ResenaPublicaRespuesta":
        return cls(**cls.campos(resena, idioma))

    def a_json(self) -> dict[str, Any]:
        # Los aspectos no calificados no se envían (el contrato no admite null en ellos).
        datos = self.model_dump(mode="json")
        datos["aspectos"] = self.aspectos.model_dump(exclude_none=True)
        return datos
