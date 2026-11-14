from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.promedio_aspecto_respuesta import PromedioAspectoRespuesta
from app.application.dto.resumen_servicio import ResumenServicio


class ResumenServicioRespuesta(BaseModel):
    """Calificación de un servicio (contrato `ResumenServicio`)."""

    servicio_id: UUID
    total: int
    promedio: float | None
    distribucion: dict[str, int]
    aspectos: dict[str, PromedioAspectoRespuesta]

    @classmethod
    def desde(cls, resumen: ResumenServicio) -> "ResumenServicioRespuesta":
        return cls(
            servicio_id=resumen.servicio_id,
            total=resumen.total,
            promedio=float(resumen.promedio) if resumen.promedio is not None else None,
            distribucion={str(n): c for n, c in resumen.distribucion.items()},
            aspectos={
                a.value: PromedioAspectoRespuesta(promedio=float(p.promedio), total=p.total)
                for a, p in resumen.aspectos.items()
            },
        )
