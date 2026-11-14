import logging

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.dto.visita_finalizada import VisitaFinalizada
from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo

logger = logging.getLogger(__name__)

CONSUMIDOR = "review.elegibilidad"


class RegistrarVisita:
    """`reserva.finalizada` de booking → el turista puede reseñar el servicio (RF-14).

    Guarda la visita más reciente: es el mes que mostrará la reseña al escribirla o editarla.
    Desde aquí el servicio aparece en `/turista/pendientes` y `POST /resenas` lo admite.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(self, visita: VisitaFinalizada) -> ResultadoConsumo:
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(visita.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            elegibilidad = await uow.elegibilidades.obtener(visita.turista_id, visita.servicio_id)
            if elegibilidad is None:
                elegibilidad = ElegibilidadResena(
                    turista_id=visita.turista_id,
                    servicio_id=visita.servicio_id,
                    ultima_visita=visita.fecha,
                )
            elif not elegibilidad.registrar_visita(visita.fecha):
                logger.info(
                    "Visita del %s no es más reciente que la registrada; se ignora", visita.fecha
                )
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            await uow.elegibilidades.guardar(elegibilidad)
            await uow.confirmar()
        return ResultadoConsumo.APLICADO
