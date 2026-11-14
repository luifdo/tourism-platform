from app.api.schemas.pagina_servicios_respuesta import PaginaServiciosRespuesta
from app.application.dto.pagina_servicios import PaginaServicios
from app.domain.value_objects.idioma import Idioma


class ResultadoBusquedaRespuesta(PaginaServiciosRespuesta):
    """Con `fecha`, cada resultado trae `cupos_disponibles` y `disponibilidad_confirmada`."""

    @classmethod
    def desde(cls, pagina: PaginaServicios, idioma: Idioma) -> "ResultadoBusquedaRespuesta":
        base = PaginaServiciosRespuesta.desde(pagina, idioma)
        return cls(**base.model_dump())
