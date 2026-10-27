from pydantic import BaseModel

from app.application.dto.reservas_por_estado import ReservasPorEstado


class ReservasPorEstadoRespuesta(BaseModel):
    solicitadas: int
    confirmadas: int
    rechazadas: int
    canceladas: int
    finalizadas: int

    @classmethod
    def desde(cls, reservas: ReservasPorEstado) -> "ReservasPorEstadoRespuesta":
        return cls(
            solicitadas=reservas.solicitadas,
            confirmadas=reservas.confirmadas,
            rechazadas=reservas.rechazadas,
            canceladas=reservas.canceladas,
            finalizadas=reservas.finalizadas,
        )
