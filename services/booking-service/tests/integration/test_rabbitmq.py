"""Paso 5.3b: publicación real en RabbitMQ (publisher confirms) y el camino completo
petición -> outbox -> relay -> RabbitMQ."""

import asyncio
import json

import aio_pika
import pytest

from infrastructure.http import demo
from infrastructure.messaging.rabbitmq import PublicadorRabbitMQ
from infrastructure.messaging.relay import RelayOutbox
from infrastructure.messaging.sobre import armar_sobre
from domain.eventos import EventoDominio

TURISTA = {"X-Usuario-Id": str(demo.USUARIO_TURISTA_DEMO), "X-Usuario-Rol": "Turista"}


async def cola_temporal(conexion, exchange: str, clave: str):
    """Una cola exclusiva (se borra sola al cerrar) enlazada a `clave`, para ver qué llega."""
    canal = await conexion.channel()
    ex = await canal.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)
    cola = await canal.declare_queue(exclusive=True)
    await cola.bind(ex, routing_key=clave)
    return cola


async def recibir(cola, cuantos: int, segundos: float = 5) -> list[aio_pika.IncomingMessage]:
    mensajes = []
    limite = asyncio.get_running_loop().time() + segundos
    while len(mensajes) < cuantos and asyncio.get_running_loop().time() < limite:
        mensaje = await cola.get(no_ack=True, fail=False)
        if mensaje is None:
            await asyncio.sleep(0.05)
        else:
            mensajes.append(mensaje)
    return mensajes


async def test_publica_el_sobre_completo_y_persistente(rabbitmq):
    cola = await cola_temporal(rabbitmq, rabbitmq.exchange_prueba, "reserva.#")
    sobre = armar_sobre(EventoDominio("reserva.confirmada", {"reserva_id": "r-1", "nota": "Ñandú"}), "corr-1")

    await PublicadorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba).publicar([sobre])  # vuelve tras el confirm

    [mensaje] = await recibir(cola, 1)
    assert json.loads(mensaje.body) == sobre
    assert mensaje.routing_key == "reserva.confirmada"
    assert mensaje.message_id == sobre["event_id"] and mensaje.correlation_id == "corr-1"
    assert mensaje.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert mensaje.content_type == "application/json" and mensaje.type == "reserva.confirmada"


async def test_la_clave_de_enrutamiento_es_el_tipo(rabbitmq):
    """Un consumidor enlazado a disponibilidad.* no recibe los reserva.*."""
    cola = await cola_temporal(rabbitmq, rabbitmq.exchange_prueba, "disponibilidad.*")
    publicador = PublicadorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba)
    await publicador.publicar([
        armar_sobre(EventoDominio("reserva.solicitada", {}), None),
        armar_sobre(EventoDominio("disponibilidad.actualizada", {"version": 2}), None),
    ])
    mensajes = await recibir(cola, 2, segundos=1)
    assert [m.routing_key for m in mensajes] == ["disponibilidad.actualizada"]


async def test_si_la_conexion_se_cerro_publicar_lanza(rabbitmq):
    """Sin confirmación no hay éxito: el relay lo cuenta como intento fallido y no lo marca."""
    publicador = PublicadorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba)
    await publicador.publicar([armar_sobre(EventoDominio("reserva.solicitada", {}), None)])
    await rabbitmq.close()
    with pytest.raises(Exception):
        await publicador.publicar([armar_sobre(EventoDominio("reserva.solicitada", {}), None)])


async def test_de_la_peticion_a_rabbitmq(cliente, motor, rabbitmq, outbox):
    """Solicitar por HTTP -> eventos en el outbox -> una vuelta del relay -> llegan a RabbitMQ en orden."""
    cola = await cola_temporal(rabbitmq, rabbitmq.exchange_prueba, "#")
    r = await cliente.post(
        "/api/bookings",
        json={"servicio_id": str(demo.SERVICIO_DEMO), "fecha_reserva": "2026-11-10", "numero_personas": 2},
        headers=TURISTA,
    )
    assert r.status_code == 201

    relay = RelayOutbox(motor, PublicadorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba))
    assert await relay.una_vuelta() == 3
    assert await outbox() == []  # ya no queda nada pendiente

    mensajes = await recibir(cola, 3)
    assert [m.routing_key for m in mensajes] == ["reserva.solicitada", "auditoria.registrada", "disponibilidad.actualizada"]
    assert json.loads(mensajes[0].body)["payload"]["reserva_id"] == r.json()["id"]
