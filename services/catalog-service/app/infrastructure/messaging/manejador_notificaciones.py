"""Traduce los `reserva.*` de la cola `catalog.notificaciones` a su caso de uso (correos)."""

from app.application.dto.reserva_notificada import ReservaNotificada
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.notificar_reserva import NotificarReserva
from app.domain.entities.reserva_proyeccion import TipoEventoReserva
from app.domain.value_objects.identidad import Rol
from app.infrastructure.messaging.esquemas.reserva_notificacion_payload import (
    ReservaNotificacionPayload,
)
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "catalog.notificaciones"
# `reserva.finalizada` no envía correo (la invitación a reseñar queda para después).
CLAVES = tuple(t.value for t in TipoEventoReserva if t is not TipoEventoReserva.FINALIZADA)


class ManejadorNotificaciones:
    def __init__(self, notificar: NotificarReserva) -> None:
        self._notificar = notificar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        if sobre.event_type not in CLAVES:
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
        datos = ReservaNotificacionPayload.model_validate(sobre.payload)
        return await self._notificar.execute(
            ReservaNotificada(
                event_id=sobre.event_id,
                tipo=TipoEventoReserva(sobre.event_type),
                reserva_id=datos.reserva_id,
                servicio_id=datos.servicio_id,
                turista_id=datos.turista_id,
                fecha_reserva=datos.fecha_reserva,
                numero_personas=datos.numero_personas,
                motivo=datos.motivo,
                cancelada_por=Rol(datos.cancelada_por) if datos.cancelada_por else None,
                fecha_anterior=datos.fecha_anterior,
                numero_personas_anterior=datos.numero_personas_anterior,
                expira_en=datos.expira_en,
            )
        )
