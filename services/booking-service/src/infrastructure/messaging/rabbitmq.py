"""RabbitMQ con aio-pika: la topología que declara booking y el publicador con confirmación.

Convenciones del equipo (contracts/events/README.md): exchange `turismo.eventos`, tipo topic,
clave de enrutamiento = `event_type`.

Declarar algo que ya existe con los mismos parámetros no hace nada, así que cada réplica
puede declarar la topología al arrancar sin coordinarse con las demás.
"""

import json
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractRobustConnection


async def conectar(url: str) -> AbstractRobustConnection:
    """Conexión que se reconecta sola si RabbitMQ se reinicia (y vuelve a declarar lo declarado)."""
    return await aio_pika.connect_robust(url, client_properties={"connection_name": "booking-service"})


async def declarar_exchange(canal: AbstractChannel, nombre: str) -> AbstractExchange:
    return await canal.declare_exchange(nombre, aio_pika.ExchangeType.TOPIC, durable=True)


class PublicadorRabbitMQ:
    """Publica sobres ya armados con *publisher confirms*: `publicar` solo vuelve cuando
    RabbitMQ confirmó que tiene el mensaje; si lo rechaza o se corta la conexión, lanza."""

    def __init__(self, conexion: AbstractRobustConnection, exchange: str):
        self._conexion = conexion
        self._nombre_exchange = exchange
        self._exchange: AbstractExchange | None = None

    async def _el_exchange(self) -> AbstractExchange:
        if self._exchange is None:
            canal = await self._conexion.channel(publisher_confirms=True)
            self._exchange = await declarar_exchange(canal, self._nombre_exchange)
        return self._exchange

    async def publicar(self, sobres: list[dict[str, Any]]) -> None:
        exchange = await self._el_exchange()
        for sobre in sobres:
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(sobre, ensure_ascii=False).encode("utf-8"),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # sobrevive a un reinicio del broker
                    message_id=sobre["event_id"],  # los consumidores deduplican por él
                    type=sobre["event_type"],
                    correlation_id=sobre.get("correlation_id"),
                ),
                routing_key=sobre["event_type"],
            )
