from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.tablero import Tablero
from app.application.ports.consulta_alertas import ConsultaAlertas
from app.application.ports.consulta_analitica import ConsultaAnalitica
from app.application.use_cases.consultar_capacidad import ConsultarCapacidad
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad

ZONAS_EN_EL_TABLERO = 5


class VerTablero:
    """UC25: tablero de planificación de la Entidad.

    Totales del rango (por fecha de la visita), capacidad de hoy por zona (UC24), las zonas
    más demandadas con sus intenciones de visita y cuántas alertas están vigentes ahora.
    """

    def __init__(
        self,
        analitica: ConsultaAnalitica,
        capacidad: ConsultarCapacidad,
        alertas: ConsultaAlertas,
        reloj: Reloj,
    ) -> None:
        self._analitica = analitica
        self._capacidad = capacidad
        self._alertas = alertas
        self._reloj = reloj

    async def execute(self, identidad: Identidad, rango: RangoFechas) -> Tablero:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        return Tablero(
            rango=rango,
            totales=await self._analitica.totales(rango),
            capacidad_hoy=tuple(await self._capacidad.execute(identidad)),
            zonas_mas_demandadas=tuple(
                await self._analitica.zonas_mas_demandadas(rango, ZONAS_EN_EL_TABLERO)
            ),
            alertas_vigentes=len(await self._alertas.vigentes(self._reloj.ahora())),
        )
