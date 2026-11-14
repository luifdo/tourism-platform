from pydantic import BaseModel

from app.api.schemas.servicio_resumen_respuesta import ServicioResumenRespuesta
from app.application.dto.pagina_servicios import PaginaServicios
from app.domain.value_objects.idioma import Idioma


class PaginaServiciosRespuesta(BaseModel):
    items: list[ServicioResumenRespuesta]
    pagina: int
    tamano: int
    total: int

    @classmethod
    def desde(cls, pagina: PaginaServicios, idioma: Idioma) -> "PaginaServiciosRespuesta":
        return cls(
            items=[ServicioResumenRespuesta.desde(s, idioma) for s in pagina.items],
            pagina=pagina.pagina,
            tamano=pagina.tamano,
            total=pagina.total,
        )
