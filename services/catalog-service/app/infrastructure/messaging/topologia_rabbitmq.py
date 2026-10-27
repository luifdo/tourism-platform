"""Topología compartida de RabbitMQ (Plan §4.2 y §4.3, ADR-008).

Cada servicio la declara al arrancar con los mismos argumentos; declararla otra vez no
cambia nada. Las colas de cada consumidor (`catalog.prestadores`, `catalog.demanda`...) las
declaran sus consumidores.
"""

from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange

EXCHANGE_DLX = "turismo.dlx"
COLA_DLQ = "turismo.dead-letter"


async def declarar_topologia(canal: AbstractChannel, exchange_eventos: str) -> AbstractExchange:
    """Exchange de eventos (`topic`, clave = `event_type`) y la DLQ común; devuelve el primero."""
    eventos = await canal.declare_exchange(exchange_eventos, ExchangeType.TOPIC, durable=True)
    dlx = await canal.declare_exchange(EXCHANGE_DLX, ExchangeType.TOPIC, durable=True)
    dlq = await canal.declare_queue(COLA_DLQ, durable=True)
    await dlq.bind(dlx, routing_key="#")
    return eventos
