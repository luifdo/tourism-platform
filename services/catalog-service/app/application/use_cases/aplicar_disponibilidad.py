import logging

from app.application.dto.disponibilidad_recibida import DisponibilidadRecibida
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.entities.disponibilidad_dia import DisponibilidadDia

logger = logging.getLogger(__name__)

CONSUMIDOR = "catalog.disponibilidad"


class AplicarDisponibilidad:
    """`disponibilidad.actualizada` de booking → proyección para filtrar por fecha y personas.

    No invalida la caché: las búsquedas y mapas con `fecha` no se cachean, porque los cupos
    cambian con cada reserva.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(self, recibida: DisponibilidadRecibida) -> ResultadoConsumo:
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(recibida.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            dia = await uow.disponibilidad.obtener(recibida.servicio_id, recibida.fecha)
            if dia is None:
                dia = DisponibilidadDia(
                    servicio_id=recibida.servicio_id,
                    fecha=recibida.fecha,
                    cupos_totales=recibida.cupos_totales,
                    cupos_disponibles=recibida.cupos_disponibles,
                    version=recibida.version,
                )
            elif not dia.aplicar(
                recibida.cupos_totales, recibida.cupos_disponibles, recibida.version
            ):
                logger.info(
                    "Disponibilidad vieja de %s el %s: se ignora",
                    recibida.servicio_id,
                    recibida.fecha,
                )
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            await uow.disponibilidad.guardar(dia)
            await uow.confirmar()
        return ResultadoConsumo.APLICADO
