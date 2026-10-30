import logging

from app.application.dto.dueno_publicado import DuenoPublicado
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.domain.entities.servicio_dueno import ServicioDueno
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo

logger = logging.getLogger(__name__)

CONSUMIDOR = "review.servicios"


class RegistrarDuenoServicio:
    """`servicio.publicado` de catalog → qué prestador es dueño del servicio.

    Lo usan la respuesta a una reseña (UC21) y el reporte del dueño (UC39). Review no llama
    a catalog: guarda esta proyección y descarta las versiones viejas, así el orden de
    llegada no importa.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(self, dueno: DuenoPublicado) -> ResultadoConsumo:
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(dueno.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            servicio = await uow.servicios.obtener(dueno.servicio_id)
            if servicio is None:
                servicio = ServicioDueno(
                    servicio_id=dueno.servicio_id,
                    prestador_usuario_id=dueno.prestador_usuario_id,
                    version=dueno.version,
                )
            elif not servicio.aplicar(dueno.version, dueno.prestador_usuario_id):
                logger.info(
                    "Versión %d del servicio %s ya superada; se ignora",
                    dueno.version,
                    dueno.servicio_id,
                )
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            await uow.servicios.guardar(servicio)
            await uow.confirmar()
        return ResultadoConsumo.APLICADO
