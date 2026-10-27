from datetime import date

from pydantic import BaseModel

from app.api.schemas.metricas_servicio_respuesta import MetricasServicioRespuesta
from app.application.dto.metricas_prestador import MetricasPrestador
from app.domain.value_objects.idioma import Idioma


class MetricasPrestadorRespuesta(BaseModel):
    desde: date
    hasta: date
    servicios: list[MetricasServicioRespuesta]

    @classmethod
    def desde_dto(cls, m: MetricasPrestador, idioma: Idioma) -> "MetricasPrestadorRespuesta":
        return cls(
            desde=m.rango.desde,
            hasta=m.rango.hasta,
            servicios=[MetricasServicioRespuesta.desde(s, idioma) for s in m.servicios],
        )
