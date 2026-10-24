"""RabbitMQ con aio-pika: la topología que declara booking y el publicador con confirmación.

Convenciones del equipo (contracts/events/README.md y Plan §4.3):
* exchange `turismo.eventos`, tipo topic, clave de enrutamiento = `event_type`;
* DLX `turismo.dlx` (topic) con la cola común `turismo.dead-letter` enlazada a `#`;
* cada consumidor declara su propia cola (`<servicio>.<propósito>`).

Declarar algo que ya existe con los mismos parámetros no hace nada, así que cada réplica (y
cada servicio) puede declarar la topología al arrancar sin coordinarse con los demás. Los
argumentos son **los mismos que declara catalog-service**: si difirieran, RabbitMQ rechazaría
la segunda declaración (PRECONDITION_FAILED).
"""

import json
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue, AbstractRobustConnection

DLX = "turismo.dlx"
COLA_MUERTOS = "turismo.dead-letter"
COLA_SERVICIOS = "booking.servicios"  # Guía §5: debe existir antes de que catalog publique
CLAVE_SERVICIOS = "servicio.publicado"


async def conectar(url: str) -> AbstractRobustConnection:
    """Conexión que se reconecta sola si RabbitMQ se reinicia (y vuelve a declarar lo declarado)."""
    return await aio_pika.connect_robust(url, client_properties={"connection_name": "booking-service"})


async def declarar_exchange(canal: AbstractChannel, nombre: str) -> AbstractExchange:
    return await canal.declare_exchange(nombre, aio_pika.ExchangeType.TOPIC, durable=True)


async def declarar_dlq(canal: AbstractChannel) -> AbstractExchange:
    """La DLX y la DLQ comunes del equipo; devuelve la DLX."""
    dlx = await canal.declare_exchange(DLX, aio_pika.ExchangeType.TOPIC, durable=True)
    muertos = await canal.declare_queue(COLA_MUERTOS, durable=True)
    await muertos.bind(dlx, routing_key="#")
    return dlx


def cola_de_reintento(cola: str, espera_s: float) -> str:
    return f"{cola}.reintento.{espera_s:g}s"  # p. ej. booking.servicios.reintento.5s


async def declarar_cola_consumidor(
    canal: AbstractChannel, exchange: str, cola: str, claves: list[str], esperas_s: tuple[float, ...]
) -> AbstractQueue:
    """La cola durable del consumidor, enlazada a sus claves, y sus colas de reintento.

    Cada cola de reintento retiene el mensaje `espera` segundos (TTL) y al vencer lo devuelve
    a la cola principal; así un fallo pasajero (la base reiniciándose) se reintenta a los 1, 5
    y 25 s sin bloquear los demás mensajes. Si la cola principal rechaza un mensaje, RabbitMQ
    lo lleva a la DLX (`x-dead-letter-exchange`).
    """
    eventos = await declarar_exchange(canal, exchange)
    await declarar_dlq(canal)
    principal = await canal.declare_queue(cola, durable=True, arguments={"x-dead-letter-exchange": DLX})
    for clave in claves:
        await principal.bind(eventos, routing_key=clave)
    for espera in esperas_s:
        await canal.declare_queue(
            cola_de_reintento(cola, espera),
            durable=True,
            arguments={
                "x-message-ttl": int(espera * 1000),
                "x-dead-letter-exchange": "",  # el exchange por defecto entrega por nombre de cola
                "x-dead-letter-routing-key": cola,
            },
        )
    return principal


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
