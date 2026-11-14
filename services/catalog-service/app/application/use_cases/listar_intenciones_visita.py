from app.application.dto.intenciones_zona_dia import IntencionesZonaDia
from app.application.dto.rango_fechas import RangoFechas
from app.application.ports.contador_intenciones import ContadorIntenciones
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class ListarIntencionesVisita:
    """Intenciones de visita por zona y día para la Entidad (indicador aparte de UC24)."""

    def __init__(self, contador: ContadorIntenciones) -> None:
        self._contador = contador

    async def execute(
        self, identidad: Identidad, rango: RangoFechas, zona: str | None = None
    ) -> list[IntencionesZonaDia]:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        return await self._contador.por_zona(rango, zona)
