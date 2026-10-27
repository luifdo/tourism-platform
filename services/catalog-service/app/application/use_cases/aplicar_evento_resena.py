import logging

from app.application.dto.resena_recibida import ResenaRecibida
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.entities.calificacion_resena import CalificacionResena

logger = logging.getLogger(__name__)

CONSUMIDOR = "catalog.calificaciones"


class AplicarEventoResena:
    """`resena.publicada` / `resena.ocultada` de review-service → proyección `calificacion_resena`.

    El promedio se calcula al leer, solo con las reseñas visibles (UC22). No invalida la
    caché: el promedio nuevo se ve cuando expira (300 s), así una ola de reseñas en temporada
    alta no borra la caché del catálogo justo cuando más se necesita (ESC-02).
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(self, resena: ResenaRecibida) -> ResultadoConsumo:
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(resena.event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            calificacion = await uow.calificaciones.obtener(resena.resena_id)
            if calificacion is None:
                # También si la ocultación llega antes que la publicación.
                calificacion = CalificacionResena.desde_evento(
                    resena.resena_id,
                    resena.servicio_id,
                    resena.puntuacion,
                    resena.visible,
                    resena.ocurrido_en,
                )
            elif not calificacion.aplicar(resena.puntuacion, resena.visible, resena.ocurrido_en):
                logger.info("Evento viejo de la reseña %s: se ignora", resena.resena_id)
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            await uow.calificaciones.guardar(calificacion)
            await uow.confirmar()
        return ResultadoConsumo.APLICADO
