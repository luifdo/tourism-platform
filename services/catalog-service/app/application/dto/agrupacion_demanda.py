from enum import StrEnum


class AgrupacionDemanda(StrEnum):
    """Periodo de la serie de demanda: las semanas empiezan el lunes y los meses el día 1."""

    DIA = "dia"
    SEMANA = "semana"
    MES = "mes"
