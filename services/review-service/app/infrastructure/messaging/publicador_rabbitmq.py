"""Publicador de eventos en RabbitMQ con *publisher confirms* (implementa PublicadorEventos).

* Mensajes persistentes, clave de enrutamiento = `event_type`, cuerpo = el sobre común
  (`contracts/events/envelope.v1.json`) y sus datos también como propiedades AMQP
  (`message_id`, `type`, `correlation_id`) para filtrarlos en la consola sin abrir el cuerpo.
* Se conecta en el primer envío y se reconecta solo (`connect_robust`): si RabbitMQ no está
  al arrancar, el envío falla, el evento sigue en el outbox y el relay reintenta.
* `mandatory=False`: si todavía nadie enlazó una cola a esa clave, el broker lo descarta en
  silencio en lugar de devolverlo. Por eso cada consumidor declara su cola durable antes de
  que haga falta.
"""

import asyncio
import json
from datetime import datetime

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractRobustConnection

from app.application.dto.evento_pendiente import EventoPendiente
from app.infrastructure.messaging.topologia_rabbitmq import declarar_topologia


class PublicadorRabbitMQ:
    def __init__(self, url: str, exchange: str, timeout_segundos: float) -> None:
        self._url = url
        self._nombre_exchange = exchange
        self._timeout = timeout_segundos
        self._conexion: AbstractRobustConnection | None = None
        self._exchange: AbstractExchange | None = None
        self._candado = asyncio.Lock()

    async def publicar(self, evento: EventoPendiente) -> None:
        exchange = await self._exchange_listo()
        sobre = evento.sobre
        mensaje = aio_pika.Message(
            body=json.dumps(sobre, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=str(evento.event_id),
            type=evento.event_type,
            correlation_id=sobre.get("correlation_id"),
            app_id=sobre.get("producer"),
            timestamp=datetime.fromisoformat(sobre["occurred_at"]),
        )
        # Con confirms, publish vuelve cuando el broker guardó el mensaje; si lo rechaza o no
        # responde a tiempo, lanza una excepción y el evento queda pendiente.
        await exchange.publish(
            mensaje, routing_key=evento.event_type, mandatory=False, timeout=self._timeout
        )

    async def cerrar(self) -> None:
        if self._conexion is not None:
            await self._conexion.close()
        self._conexion = self._exchange = None

    async def _exchange_listo(self) -> AbstractExchange:
        async with self._candado:
            if self._exchange is None:
                self._conexion = await aio_pika.connect_robust(self._url, timeout=self._timeout)
                canal = await self._conexion.channel(publisher_confirms=True)
                self._exchange = await declarar_topologia(canal, self._nombre_exchange)
            return self._exchange
