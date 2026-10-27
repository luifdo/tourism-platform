"""Traduce los eventos de review de la cola `catalog.calificaciones` a su caso de uso."""

from app.application.dto.resena_recibida import ResenaRecibida
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.aplicar_evento_resena import AplicarEventoResena
from app.infrastructure.messaging.esquemas.resena_payload import ResenaPayload
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "catalog.calificaciones"
# Clave → la reseña queda visible (cuenta en el promedio) o no.
VISIBLE_POR_CLAVE = {"resena.publicada": True, "resena.ocultada": False}
CLAVES = tuple(VISIBLE_POR_CLAVE)


class ManejadorCalificaciones:
    def __init__(self, aplicar: AplicarEventoResena) -> None:
        self._aplicar = aplicar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        visible = VISIBLE_POR_CLAVE.get(sobre.event_type)
        if visible is None:
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
        resena = ResenaPayload.model_validate(sobre.payload)
        return await self._aplicar.execute(
            ResenaRecibida(
                event_id=sobre.event_id,
                ocurrido_en=sobre.occurred_at,
                resena_id=resena.resena_id,
                servicio_id=resena.servicio_id,
                puntuacion=resena.puntuacion,
                visible=visible,
            )
        )
