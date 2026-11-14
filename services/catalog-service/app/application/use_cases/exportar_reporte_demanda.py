from collections.abc import AsyncIterator

from app.application.dto.fila_reporte_demanda import FilaReporteDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.ports.consulta_analitica import ConsultaAnalitica
from app.application.ports.consulta_zonas import ConsultaZonas
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.errors import NoEncontrado
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class ExportarReporteDemanda:
    """UC38: reporte de demanda para el personal de la Entidad (por fecha de la visita).

    La exportación se audita (`auditoria.registrada`, acción `EXPORT`) antes de entregar el
    archivo: queda constancia de quién sacó datos del destino, con qué filtros, aunque la
    descarga se corte a la mitad.
    """

    def __init__(
        self,
        analitica: ConsultaAnalitica,
        zonas: ConsultaZonas,
        unidad_de_trabajo: FabricaUnidadDeTrabajo,
        reloj: Reloj,
    ) -> None:
        self._analitica = analitica
        self._zonas = zonas
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self, identidad: Identidad, rango: RangoFechas, zona: str | None = None
    ) -> AsyncIterator[FilaReporteDemanda]:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        if zona is not None and zona not in {z.codigo for z in await self._zonas.activas()}:
            raise NoEncontrado(recurso="zona", id=zona)
        async with self._uow() as uow:
            await uow.outbox.agregar(
                AuditoriaRegistrada(
                    usuario_id=identidad.usuario_id,
                    accion="EXPORT",
                    detalles={
                        "reporte": "demanda",
                        "formato": "csv",
                        "desde": rango.desde.isoformat(),
                        "hasta": rango.hasta.isoformat(),
                        "zona": zona,
                    },
                    ocurrido_en=self._reloj.ahora(),
                )
            )
            await uow.confirmar()
        return self._analitica.filas_reporte_demanda(rango, zona)
