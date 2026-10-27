from enum import StrEnum

UMBRAL_MEDIO = 0.60
UMBRAL_ALTO = 0.85  # bandera de advertencia (Plan §2.3)


class NivelSaturacion(StrEnum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"

    @classmethod
    def desde_indice(cls, indice: float) -> "NivelSaturacion":
        if indice >= UMBRAL_ALTO:
            return cls.ALTO
        if indice >= UMBRAL_MEDIO:
            return cls.MEDIO
        return cls.BAJO
