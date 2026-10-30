from pydantic import BaseModel

from app.api.schemas.punto_demanda_respuesta import PuntoDemandaRespuesta
from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.serie_demanda import SerieDemanda


class SerieDemandaRespuesta(BaseModel):
    agrupacion: AgrupacionDemanda
    serie: list[PuntoDemandaRespuesta]

    @classmethod
    def desde(cls, s: SerieDemanda) -> "SerieDemandaRespuesta":
        return cls(agrupacion=s.agrupacion, serie=[PuntoDemandaRespuesta.desde(p) for p in s.serie])
