from enum import StrEnum


class MotivoReporte(StrEnum):
    OFENSIVO = "OFENSIVO"
    SPAM = "SPAM"
    FALSO = "FALSO"
    DATOS_PERSONALES = "DATOS_PERSONALES"
    OTRO = "OTRO"
