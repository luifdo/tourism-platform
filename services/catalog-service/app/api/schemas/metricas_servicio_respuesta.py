from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.reservas_por_estado_respuesta import ReservasPorEstadoRespuesta
from app.application.dto.metricas_servicio import MetricasServicio
from app.domain.value_objects.idioma import Idioma


class MetricasServicioRespuesta(BaseModel):
    servicio_id: UUID
    nombre: str
    reservas: ReservasPorEstadoRespuesta
    personas_finalizadas: int
    ocupacion: float
    calificacion_promedio: float | None
    total_resenas: int
    intenciones_visita: int

    @classmethod
    def desde(cls, m: MetricasServicio, idioma: Idioma) -> "MetricasServicioRespuesta":
        return cls(
            servicio_id=m.servicio_id,
            nombre=m.nombre.en_idioma(idioma)[0],
            reservas=ReservasPorEstadoRespuesta.desde(m.reservas),
            personas_finalizadas=m.personas_finalizadas,
            ocupacion=m.ocupacion,
            calificacion_promedio=m.calificacion_promedio,
            total_resenas=m.total_resenas,
            intenciones_visita=m.intenciones_visita,
        )
