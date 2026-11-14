from enum import StrEnum


class EstadoAlerta(StrEnum):
    """Estado de una alerta en el panel de la Entidad (se calcula con la hora actual)."""

    VIGENTE = "VIGENTE"
    VENCIDA = "VENCIDA"
    RETIRADA = "RETIRADA"
