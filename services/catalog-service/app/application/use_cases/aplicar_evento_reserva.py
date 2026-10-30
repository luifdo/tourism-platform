import logging
from uuid import UUID

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.entities.reserva_proyeccion import EventoReserva, ReservaProyeccion

logger = logging.getLogger(__name__)

CONSUMIDOR = "catalog.demanda"


class AplicarEventoReserva:
    """`reserva.*` de booking-service → proyección `reserva_proyeccion` (demanda por día).

    Se guarda el estado actual de cada reserva, no contadores: un evento repetido o
    desordenado no descuadra nada. La demanda de un día es la suma de las reservas activas
    (Solicitada y Confirmada) de esa fecha. catalog nunca consulta `booking_db`.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo) -> None:
        self._uow = unidad_de_trabajo

    async def execute(self, event_id: UUID, evento: EventoReserva) -> ResultadoConsumo:
        async with self._uow() as uow:
            if not await uow.eventos_procesados.registrar(event_id, CONSUMIDOR):
                return ResultadoConsumo.DUPLICADO
            reserva = await uow.reservas.obtener(evento.reserva_id)
            if reserva is None:
                # También si llega, por ejemplo, la confirmación antes que la solicitud.
                reserva = ReservaProyeccion.desde_evento(evento)
            elif not reserva.aplicar(evento):
                logger.info("%s viejo para %s: se ignora", evento.tipo, evento.reserva_id)
                await uow.confirmar()  # queda registrado como procesado
                return ResultadoConsumo.IGNORADO
            await uow.reservas.guardar(reserva)
            await uow.confirmar()
        return ResultadoConsumo.APLICADO
