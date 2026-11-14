"""Consumidor genérico de una cola de RabbitMQ con reintentos y DLQ (Plan §4.3, ADR-008).

Lo usan todas las colas de catalog (`catalog.prestadores`, `catalog.demanda`...):

* **Cola principal** durable, enlazada a sus claves en `turismo.eventos`.
* **Reintentos** con espera de 1 s, 5 s y 25 s: una cola por espera, con TTL, que al vencer
  devuelve el mensaje a la cola principal (`x-dead-letter-routing-key`). El número de intento
  viaja en la cabecera `x-intentos`.
* **DLQ:** tras el 3.er fallo, o de inmediato si el mensaje no cumple el contrato, se publica
  en `turismo.dlx` (cola `turismo.dead-letter`) con la cola, los intentos y el error.
* El mensaje original se reconoce (`ack`) solo después de copiarlo al reintento o a la DLQ;
  si esa copia falla, vuelve a la cola (`nack` con `requeue`) y no se pierde.
* La idempotencia por `event_id` la hace el caso de uso, en la misma transacción del efecto.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractRobustConnection,
)

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import ERRORES_PERMANENTES, EventoInvalido
from app.infrastructure.messaging.topologia_rabbitmq import EXCHANGE_DLX, declarar_topologia
from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.observabilidad.metricas_consumo import EVENTOS_CONSUMIDOS

logger = logging.getLogger(__name__)

ESPERAS_REINTENTO = (1.0, 5.0, 25.0)
VERSION_SOPORTADA = 1
_INTENTOS = "x-intentos"

Manejador = Callable[[SobreEvento], Awaitable[ResultadoConsumo]]


class ConsumidorRabbitMQ:
    def __init__(
        self,
        url: str,
        exchange: str,
        cola: str,
        claves: tuple[str, ...],
        manejar: Manejador,
        esperas: tuple[float, ...] = ESPERAS_REINTENTO,
        prefetch: int = 10,
        timeout_segundos: float = 5.0,
    ) -> None:
        self._url = url
        self._nombre_exchange = exchange
        self._cola = cola
        self._claves = claves
        self._manejar = manejar
        self._esperas = esperas
        self._prefetch = prefetch
        self._timeout = timeout_segundos
        self._conexion: AbstractRobustConnection | None = None
        self._canal: AbstractChannel | None = None
        self._dlx: AbstractExchange | None = None

    def cola_de_reintento(self, intento: int) -> str:
        return f"{self._cola}.reintento.{self._esperas[intento - 1]:g}s"

    async def iniciar(self) -> None:
        self._conexion = await aio_pika.connect_robust(self._url, timeout=self._timeout)
        canal = await self._conexion.channel(publisher_confirms=True)
        await canal.set_qos(prefetch_count=self._prefetch)
        eventos = await declarar_topologia(canal, self._nombre_exchange)
        self._dlx = await canal.declare_exchange(EXCHANGE_DLX, ExchangeType.TOPIC, durable=True)
        cola = await canal.declare_queue(
            self._cola, durable=True, arguments={"x-dead-letter-exchange": EXCHANGE_DLX}
        )
        for clave in self._claves:
            await cola.bind(eventos, routing_key=clave)
        for intento, espera in enumerate(self._esperas, start=1):
            await canal.declare_queue(
                self.cola_de_reintento(intento),
                durable=True,
                arguments={
                    "x-message-ttl": int(espera * 1000),
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": self._cola,
                },
            )
        self._canal = canal
        await cola.consume(self._procesar)
        logger.info("Consumiendo %s (%s)", self._cola, ", ".join(self._claves))

    async def cerrar(self) -> None:
        if self._conexion is not None:
            await self._conexion.close()
        self._conexion = self._canal = self._dlx = None

    async def _procesar(self, mensaje: AbstractIncomingMessage) -> None:
        intentos = int((mensaje.headers or {}).get(_INTENTOS, 0) or 0)
        tipo = mensaje.type or "desconocido"
        try:
            sobre = SobreEvento.model_validate_json(mensaje.body)
            tipo = sobre.event_type
            if sobre.version != VERSION_SOPORTADA:
                raise EventoInvalido(f"versión {sobre.version} de {tipo} no soportada")
            fijar_correlation_id(sobre.correlation_id or str(sobre.event_id))
            resultado = await self._manejar(sobre)
        except ERRORES_PERMANENTES as exc:
            logger.warning("Evento inválido en %s: %s", self._cola, exc)
            await self._a_dlq(mensaje, tipo, intentos, exc)
            return
        except Exception as exc:
            if intentos < len(self._esperas):
                logger.warning(
                    "Falló %s en %s (intento %d); se reintenta",
                    tipo,
                    self._cola,
                    intentos + 1,
                    exc_info=True,
                )
                await self._reintentar(mensaje, tipo, intentos + 1, exc)
            else:
                logger.error("Falló %s en %s tras %d intentos", tipo, self._cola, intentos + 1)
                await self._a_dlq(mensaje, tipo, intentos + 1, exc)
            return
        await mensaje.ack()
        EVENTOS_CONSUMIDOS.labels(cola=self._cola, event_type=tipo, resultado=resultado).inc()

    async def _reintentar(
        self, mensaje: AbstractIncomingMessage, tipo: str, intento: int, error: Exception
    ) -> None:
        assert self._canal is not None
        try:
            await self._canal.default_exchange.publish(
                _copia(mensaje, tipo, {_INTENTOS: intento, "x-ultimo-error": _texto(error)}),
                routing_key=self.cola_de_reintento(intento),
                timeout=self._timeout,
            )
        except Exception:
            logger.exception("No se pudo programar el reintento; el mensaje vuelve a la cola")
            await mensaje.nack(requeue=True)
            return
        await mensaje.ack()
        EVENTOS_CONSUMIDOS.labels(cola=self._cola, event_type=tipo, resultado="reintento").inc()

    async def _a_dlq(
        self, mensaje: AbstractIncomingMessage, tipo: str, intentos: int, error: Exception
    ) -> None:
        assert self._dlx is not None
        cabeceras = {"x-cola": self._cola, _INTENTOS: intentos, "x-error": _texto(error)}
        try:
            await self._dlx.publish(
                _copia(mensaje, tipo, cabeceras), routing_key=tipo, timeout=self._timeout
            )
        except Exception:
            # La cola principal tiene `x-dead-letter-exchange`: el broker lo lleva igual a
            # la DLQ, solo que sin el texto del error.
            logger.exception("No se pudo copiar a la DLQ; se rechaza el mensaje")
            await mensaje.reject(requeue=False)
        else:
            await mensaje.ack()
        EVENTOS_CONSUMIDOS.labels(cola=self._cola, event_type=tipo, resultado="dlq").inc()


def _copia(
    mensaje: AbstractIncomingMessage, tipo: str, cabeceras: dict[str, Any]
) -> aio_pika.Message:
    return aio_pika.Message(
        body=mensaje.body,
        headers={**(mensaje.headers or {}), **cabeceras},
        content_type=mensaje.content_type,
        content_encoding=mensaje.content_encoding,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        message_id=mensaje.message_id,
        type=tipo,
        correlation_id=mensaje.correlation_id,
        app_id=mensaje.app_id,
        timestamp=mensaje.timestamp,
    )


def _texto(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:500]
