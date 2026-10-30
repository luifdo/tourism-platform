from enum import StrEnum


class ResultadoConsumo(StrEnum):
    """Qué pasó con un evento recibido (etiqueta de la métrica de consumo)."""

    APLICADO = "aplicado"
    DUPLICADO = "duplicado"  # ya se había procesado ese event_id
    IGNORADO = "ignorado"  # válido, pero no aplica (más viejo que el estado actual, desconocido)
