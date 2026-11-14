from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.fila_metricas_servicio import FilaMetricasServicio
from app.application.dto.fila_reporte_demanda import FilaReporteDemanda
from app.application.dto.punto_demanda import PuntoDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.zona_demandada import ZonaDemandada
from app.domain.value_objects.catalogos import Categoria


class ConsultaAnalitica(Protocol):
    """Lectura agregada de las proyecciones (UC22, UC23, UC25), siempre por fecha de la visita.

    El estado de cada reserva es el actual: una reserva solicitada y luego confirmada cuenta
    una sola vez, como confirmada.
    """

    async def metricas_prestador(
        self, prestador_id: UUID, rango: RangoFechas
    ) -> list[FilaMetricasServicio]:
        """Todos sus servicios, apagados incluidos, por nombre."""
        ...

    async def demanda(
        self,
        rango: RangoFechas,
        agrupacion: AgrupacionDemanda,
        zona: str | None,
        categoria: Categoria | None,
    ) -> list[PuntoDemanda]:
        """Solo los periodos con reservas; el caso de uso rellena los vacíos con 0."""
        ...

    async def totales(self, rango: RangoFechas) -> PuntoDemanda: ...

    async def zonas_mas_demandadas(self, rango: RangoFechas, limite: int) -> list[ZonaDemandada]:
        """Por personas en reservas no canceladas; sin personas ni intenciones, no salen."""
        ...

    def filas_reporte_demanda(
        self, rango: RangoFechas, zona: str | None
    ) -> AsyncIterator[FilaReporteDemanda]:
        """Una fila por servicio y día con actividad, por fecha, zona y nombre; se lee en
        streaming para que un rango de un año no cargue todo en memoria."""
        ...
