from uuid import UUID

from app.api.schemas.reporte_respuesta import ReporteRespuesta
from app.api.schemas.resena_propia_respuesta import ResenaPropiaRespuesta
from app.application.dto.resena_en_moderacion import ResenaEnModeracion
from app.domain.value_objects.idioma import Idioma


class ResenaModeracionRespuesta(ResenaPropiaRespuesta):
    """Vista del Administrador (contrato `ResenaModeracion`): con el autor, para auditar, y
    los reportes sin resolver."""

    turista_id: UUID
    reportes: list[ReporteRespuesta]

    @classmethod
    def de_moderacion(cls, item: ResenaEnModeracion, idioma: Idioma) -> "ResenaModeracionRespuesta":
        propia = ResenaPropiaRespuesta.desde(item.resena, idioma)
        return cls(
            **propia.model_dump(),
            turista_id=item.resena.turista_id,
            reportes=[ReporteRespuesta.desde(r, idioma) for r in item.reportes],
        )
