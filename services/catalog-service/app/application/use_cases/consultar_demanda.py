from datetime import date, timedelta

from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.punto_demanda import PuntoDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.serie_demanda import SerieDemanda
from app.application.ports.consulta_analitica import ConsultaAnalitica
from app.application.ports.consulta_zonas import ConsultaZonas
from app.domain.errors import NoEncontrado
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


def inicio_de_periodo(dia: date, agrupacion: AgrupacionDemanda) -> date:
    """Igual que `date_trunc` de PostgreSQL: lunes para la semana, día 1 para el mes."""
    if agrupacion is AgrupacionDemanda.SEMANA:
        return dia - timedelta(days=dia.weekday())
    if agrupacion is AgrupacionDemanda.MES:
        return dia.replace(day=1)
    return dia


def periodos(rango: RangoFechas, agrupacion: AgrupacionDemanda) -> list[date]:
    resultado, actual = [], inicio_de_periodo(rango.desde, agrupacion)
    while actual <= rango.hasta:
        resultado.append(actual)
        if agrupacion is AgrupacionDemanda.MES:
            actual = (actual.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            actual += timedelta(days=7 if agrupacion is AgrupacionDemanda.SEMANA else 1)
    return resultado


class ConsultarDemanda:
    """UC23: personas que vienen al destino (o a una zona) por periodo, según el estado
    actual de su reserva. Los periodos sin reservas salen en 0, para que el gráfico no
    tenga huecos."""

    def __init__(self, analitica: ConsultaAnalitica, zonas: ConsultaZonas) -> None:
        self._analitica = analitica
        self._zonas = zonas

    async def execute(
        self,
        identidad: Identidad,
        rango: RangoFechas,
        agrupacion: AgrupacionDemanda = AgrupacionDemanda.DIA,
        zona: str | None = None,
        categoria: Categoria | None = None,
    ) -> SerieDemanda:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        if zona is not None and zona not in {z.codigo for z in await self._zonas.activas()}:
            raise NoEncontrado(recurso="zona", id=zona)
        con_datos = {
            p.periodo: p for p in await self._analitica.demanda(rango, agrupacion, zona, categoria)
        }
        serie = tuple(
            con_datos.get(periodo, PuntoDemanda(periodo=periodo, zona=zona))
            for periodo in periodos(rango, agrupacion)
        )
        return SerieDemanda(agrupacion=agrupacion, serie=serie)
