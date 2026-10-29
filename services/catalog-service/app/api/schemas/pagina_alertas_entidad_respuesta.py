from pydantic import BaseModel

from app.api.schemas.alerta_editable_respuesta import AlertaEditableRespuesta
from app.application.dto.pagina_alertas_entidad import PaginaAlertasEntidad
from app.domain.value_objects.idioma import Idioma


class PaginaAlertasEntidadRespuesta(BaseModel):
    items: list[AlertaEditableRespuesta]
    pagina: int
    tamano: int
    total: int

    @classmethod
    def desde(cls, pagina: PaginaAlertasEntidad, idioma: Idioma) -> "PaginaAlertasEntidadRespuesta":
        return cls(
            items=[AlertaEditableRespuesta.desde(a, idioma, pagina.ahora) for a in pagina.items],
            pagina=pagina.pagina,
            tamano=pagina.tamano,
            total=pagina.total,
        )
