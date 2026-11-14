from enum import StrEnum


class ResultadoConsumo(StrEnum):
    """Qué pasó con un evento recibido (etiqueta de la métrica de consumo)."""

    APLICADO = "aplicado"
    DUPLICADO = "duplicado"  # ya se había guardado ese event_id
