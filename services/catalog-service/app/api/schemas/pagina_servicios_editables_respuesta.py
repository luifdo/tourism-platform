from pydantic import BaseModel

from app.api.schemas.servicio_editable_respuesta import ServicioEditableRespuesta
from app.application.dto.pagina_servicios_editables import PaginaServiciosEditables
from app.domain.value_objects.idioma import Idioma


class PaginaServiciosEditablesRespuesta(BaseModel):
    items: list[ServicioEditableRespuesta]
    pagina: int
    tamano: int
    total: int

    @classmethod
    def desde(
        cls, pagina: PaginaServiciosEditables, idioma: Idioma
    ) -> "PaginaServiciosEditablesRespuesta":
        return cls(
            items=[ServicioEditableRespuesta.desde(s, idioma) for s in pagina.items],
            pagina=pagina.pagina,
            tamano=pagina.tamano,
            total=pagina.total,
        )
