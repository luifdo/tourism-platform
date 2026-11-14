from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.value_objects.saturacion import UMBRAL_ALTO, NivelSaturacion


@dataclass(frozen=True, slots=True)
class CargaServicio:
    """Ocupación de un servicio en una fecha: personas en reservas activas y su capacidad."""

    personas_activas: int
    capacidad_aforo_diario: int
    activo: bool


@dataclass(frozen=True, slots=True)
class ResultadoSaturacion:
    personas_activas: int
    capacidad: int
    indice: float
    nivel: NivelSaturacion

    @property
    def bandera(self) -> bool:
        return self.indice >= UMBRAL_ALTO


class CalculadoraSaturacion:
    """Índice = personas en reservas activas (Solicitada + Confirmada) ÷ capacidad de carga."""

    def de_servicio(self, carga: CargaServicio) -> ResultadoSaturacion | None:
        return self._resultado(carga.personas_activas, carga.capacidad_aforo_diario)

    def de_zona(self, cargas: Iterable[CargaServicio]) -> ResultadoSaturacion | None:
        """Suma los servicios de la zona que están activos o que tienen reservas activas.

        Un servicio desactivado con reservas vigentes sigue recibiendo personas ese día, así
        que cuenta con su capacidad; uno desactivado y sin reservas no infla la capacidad.
        """
        personas = capacidad = 0
        for carga in cargas:
            if carga.activo or carga.personas_activas > 0:
                personas += carga.personas_activas
                capacidad += carga.capacidad_aforo_diario
        return self._resultado(personas, capacidad)

    @staticmethod
    def _resultado(personas: int, capacidad: int) -> ResultadoSaturacion | None:
        if capacidad <= 0:
            return None
        indice = personas / capacidad
        return ResultadoSaturacion(
            personas_activas=personas,
            capacidad=capacidad,
            indice=round(indice, 4),
            nivel=NivelSaturacion.desde_indice(indice),
        )
