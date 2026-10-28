from datetime import datetime

from pydantic import BaseModel

from app.api.i18n.etiquetas import etiqueta
from app.domain.entities.reporte_resena import ReporteResena
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.motivo_reporte import MotivoReporte


class ReporteRespuesta(BaseModel):
    """Un reporte sin resolver, para el Administrador (contrato `Reporte`); sin quién lo hizo."""

    motivo: MotivoReporte
    motivo_etiqueta: str
    detalle: str | None
    rol_reportante: str
    es_dueno: bool
    reportado_en: datetime

    @classmethod
    def desde(cls, reporte: ReporteResena, idioma: Idioma) -> "ReporteRespuesta":
        return cls(
            motivo=reporte.motivo,
            motivo_etiqueta=etiqueta(reporte.motivo, idioma),
            detalle=reporte.detalle,
            rol_reportante=reporte.rol.value,
            es_dueno=reporte.es_dueno,
            reportado_en=reporte.reportado_en,
        )
