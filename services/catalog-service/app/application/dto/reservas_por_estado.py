from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReservasPorEstado:
    """Número de reservas del rango por su estado actual."""

    solicitadas: int = 0
    confirmadas: int = 0
    rechazadas: int = 0
    canceladas: int = 0
    finalizadas: int = 0
