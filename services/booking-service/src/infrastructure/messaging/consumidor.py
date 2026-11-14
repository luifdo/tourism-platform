"""Consumidor de RabbitMQ con reintentos y DLQ (Plan §4.3), y el manejador de `servicio.publicado`.

Para cada mensaje:
* **Bien procesado:** `ack`.
* **Error permanente** (JSON roto, tipo o versión desconocidos, payload que no cumple el
  contrato): reintentar no lo arreglaría; va directo a la DLQ.
* **Error pasajero** (la base no responde...): se copia a la cola de reintento de 1 s, luego
  5 s y luego 25 s; el número de intento viaja en la cabecera `x-intentos`. Tras el tercero,
  a la DLQ `turismo.dead-letter` con la cola, los intentos y el error en las cabeceras.
* El original se reconoce (`ack`) solo **después** de copiarlo al reintento o a la DLQ; si la
  copia falla, vuelve a la cola (`nack` con `requeue`) y no se pierde.

Es la misma convención (nombres de colas y cabeceras) que usa catalog-service.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractIncomingMessage, AbstractQueue, AbstractRobustConnection

from application.base import Contexto
from application.servicios import AplicarServicioPublicado
from infrastructure.http.operacion import EVENTOS_CONSUMIDOS
from infrastructure.messaging.esquemas import ServicioPublicado
from infrastructure.messaging.rabbitmq import cola_de_reintento, declarar_cola_consumidor, declarar_dlq

log = logging.getLogger("booking.consumidor")
ESPERAS_REINTENTO_S = (1.0, 5.0, 25.0)
INTENTOS = "x-intentos"

Manejador = Callable[[dict[str, Any]], Awaitable[bool]]  # True = aplicado, False = descartado


class ErrorPermanente(Exception):
    """El mensaje nunca se podrá procesar tal como está: no tiene sentido reintentarlo."""


class ConsumidorRabbitMQ:
    def __init__(
        self,
        conexion: AbstractRobustConnection,
        exchange: str,
        cola: str,
        claves: list[str],
        manejar: Manejador,
        esperas_s: tuple[float, ...] = ESPERAS_REINTENTO_S,
        prefetch: int = 10,
    ):
        self._conexion = conexion
        self._exchange = exchange
        self._cola = cola
        self._claves = claves
        self._manejar = manejar
        self._esperas_s = esperas_s
        self._prefetch = prefetch
        self._canal: AbstractChannel | None = None
        self._dlx: AbstractExchange | None = None
        self._principal: AbstractQueue | None = None
        self._etiqueta: str | None = None

    async def iniciar(self) -> None:
        """Declara la topología (la cola existe aunque nadie esté consumiendo) y empieza a consumir."""
        self._canal = await self._conexion.channel(publisher_confirms=True)
        await self._canal.set_qos(prefetch_count=self._prefetch)  # mensajes en vuelo por réplica
        self._principal = await declarar_cola_consumidor(
            self._canal, self._exchange, self._cola, self._claves, self._esperas_s
        )
        self._dlx = await declarar_dlq(self._canal)
        self._etiqueta = await self._principal.consume(self._procesar)

    async def detener(self) -> None:
        if self._principal is not None and self._etiqueta is not None:
            await self._principal.cancel(self._etiqueta)
        if self._canal is not None and not self._canal.is_closed:
            await self._canal.close()

    async def _procesar(self, mensaje: AbstractIncomingMessage) -> None:
        intentos = int((mensaje.headers or {}).get(INTENTOS, 0))
        tipo = mensaje.routing_key or "desconocido"
        try:
            try:
                sobre = json.loads(mensaje.body)
            except ValueError as error:
                raise ErrorPermanente(f"El cuerpo no es JSON: {error}") from error
            aplicado = await self._manejar(sobre)
        except ErrorPermanente as error:
            log.error("Mensaje inválido en %s; va a la DLQ: %s", self._cola, error)
            await self._a_dlq(mensaje, tipo, intentos, error)
        except Exception as error:
            if intentos < len(self._esperas_s):
                log.warning("Falló %s en %s (intento %d); se reintenta", tipo, self._cola, intentos + 1, exc_info=True)
                await self._reintentar(mensaje, tipo, intentos + 1, error)
            else:
                log.error("Falló %s en %s tras %d intentos; va a la DLQ", tipo, self._cola, intentos, exc_info=True)
                await self._a_dlq(mensaje, tipo, intentos, error)
        else:
            await mensaje.ack()
            EVENTOS_CONSUMIDOS.labels(self._cola, tipo, "aplicado" if aplicado else "descartado").inc()

    async def _reintentar(self, mensaje: AbstractIncomingMessage, tipo: str, intento: int, error: Exception) -> None:
        assert self._canal is not None
        try:
            await self._canal.default_exchange.publish(
                _copia(mensaje, {INTENTOS: intento, "x-ultimo-error": _texto(error)}),
                routing_key=cola_de_reintento(self._cola, self._esperas_s[intento - 1]),
            )
        except Exception:
            log.exception("No se pudo programar el reintento; el mensaje vuelve a la cola")
            await mensaje.nack(requeue=True)
            return
        await mensaje.ack()
        EVENTOS_CONSUMIDOS.labels(self._cola, tipo, "reintento").inc()

    async def _a_dlq(self, mensaje: AbstractIncomingMessage, tipo: str, intentos: int, error: Exception) -> None:
        assert self._dlx is not None
        try:
            await self._dlx.publish(
                _copia(mensaje, {"x-cola": self._cola, INTENTOS: intentos, "x-error": _texto(error)}),
                routing_key=tipo,
            )
        except Exception:
            # La cola principal tiene x-dead-letter-exchange: el broker lo lleva igual a la DLQ,
            # solo que sin el texto del error.
            log.exception("No se pudo copiar a la DLQ; se rechaza el mensaje")
            await mensaje.reject(requeue=False)
        else:
            await mensaje.ack()
        EVENTOS_CONSUMIDOS.labels(self._cola, tipo, "dlq").inc()


def _copia(mensaje: AbstractIncomingMessage, cabeceras: dict[str, Any]) -> aio_pika.Message:
    return aio_pika.Message(
        body=mensaje.body,
        headers={**(mensaje.headers or {}), **cabeceras},
        content_type=mensaje.content_type,
        message_id=mensaje.message_id,
        correlation_id=mensaje.correlation_id,
        type=mensaje.type,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )


def _texto(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:500]


# ---------- servicio.publicado.v1 -> servicio_ref ----------

def manejador_servicios(ctx: Contexto) -> Manejador:
    """Valida el sobre y el payload contra el contrato y aplica el evento a `servicio_ref`.

    Los duplicados y los desordenados no necesitan deduplicación aparte: el evento lleva el
    estado completo con su `version`, y solo se aplica si es mayor que la guardada (5.2b).
    """
    aplicar = AplicarServicioPublicado(ctx)

    async def manejar(sobre: dict[str, Any]) -> bool:
        try:
            if sobre.get("event_type") != "servicio.publicado" or sobre.get("version") != 1:
                raise ErrorPermanente(
                    f"Se esperaba servicio.publicado v1, llegó {sobre.get('event_type')} v{sobre.get('version')}"
                )
            payload = ServicioPublicado.model_validate(sobre.get("payload"))
        except (ValueError, TypeError, AttributeError) as error:  # ValidationError es ValueError
            raise ErrorPermanente(str(error)) from error
        return await aplicar(payload.model_dump(mode="json"))

    return manejar
