from datetime import date

from pydantic import BaseModel

from app.application.dto.punto_demanda import PuntoDemanda


class PuntoDemandaRespuesta(BaseModel):
    periodo: date
    zona: str | None
    personas_solicitadas: int
    personas_confirmadas: int
    personas_finalizadas: int
    personas_canceladas: int

    @classmethod
    def desde(cls, p: PuntoDemanda) -> "PuntoDemandaRespuesta":
        return cls(
            periodo=p.periodo,
            zona=p.zona,
            personas_solicitadas=p.solicitadas,
            personas_confirmadas=p.confirmadas,
            personas_finalizadas=p.finalizadas,
            personas_canceladas=p.canceladas,
        )
