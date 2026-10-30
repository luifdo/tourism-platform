"""Paso 5.3c: el consumidor contra RabbitMQ real (reintentos, DLQ) y servicio.publicado hasta Postgres."""

import asyncio
import json
import uuid
from decimal import Decimal

import aio_pika
import pytest
from sqlalchemy import delete

from application.base import Contexto
from config import Configuracion
from domain.eventos import EventoDominio
from infrastructure.messaging.arranque import Mensajeria
from infrastructure.messaging.consumidor import ConsumidorRabbitMQ, ErrorPermanente, manejador_servicios
from infrastructure.messaging.rabbitmq import (
    COLA_SERVICIOS,
    DLX,
    PublicadorRabbitMQ,
    cola_de_reintento,
    conectar,
)
from infrastructure.messaging.sobre import armar_sobre
from infrastructure.persistence.db import fabrica_sesiones
from infrastructure.persistence.postgres import RepositorioServiciosPostgres, fabrica_postgres
from infrastructure.persistence.tablas import servicio_ref
from infrastructure.reloj import RelojSistema

ESPERAS = (0.2, 0.4, 0.6)  # las reales son 1, 5 y 25 s


async def hasta_que(condicion, segundos: float = 5.0):
    limite = asyncio.get_running_loop().time() + segundos
    while asyncio.get_running_loop().time() < limite:
        if await condicion():
            return True
        await asyncio.sleep(0.05)
    return False


def servicio_publicado(version=1, servicio_id=None, **cambios):
    return armar_sobre(EventoDominio("servicio.publicado", {
        "servicio_id": str(servicio_id or uuid.uuid4()), "prestador_id": str(uuid.uuid4()),
        "prestador_usuario_id": str(uuid.uuid4()), "capacidad_aforo_diario": 20, "tarifa_base": 85000,
        "activo": True, "version": version, **cambios,
    }), "corr-servicio")


class ManejadorFalso:
    def __init__(self, fallos: int = 0, error: Exception | None = None):
        self.recibidos: list[dict] = []
        self._fallos = fallos
        self._error = error or ConnectionError("la base no responde")

    async def __call__(self, sobre):
        self.recibidos.append(sobre)
        if len(self.recibidos) <= self._fallos:
            raise self._error
        return True


@pytest.fixture
async def entorno(rabbitmq):
    """Una cola de pruebas propia, un publicador y una cola espía enlazada a la DLX."""
    cola = f"pruebas.{uuid.uuid4()}.servicios"
    canal = await rabbitmq.channel()
    espia_dlq = await canal.declare_queue(exclusive=True)
    consumidores: list[ConsumidorRabbitMQ] = []

    async def consumidor(manejar):
        c = ConsumidorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba, cola, ["servicio.publicado"], manejar, ESPERAS)
        await c.iniciar()
        await espia_dlq.bind(DLX, routing_key="#")
        consumidores.append(c)
        return c

    async def publicar(sobre_o_cuerpo, clave="servicio.publicado"):
        if isinstance(sobre_o_cuerpo, dict):
            await PublicadorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba).publicar([sobre_o_cuerpo])
        else:  # cuerpo crudo (p. ej. JSON roto)
            ex = await canal.get_exchange(rabbitmq.exchange_prueba)
            await ex.publish(aio_pika.Message(body=sobre_o_cuerpo), routing_key=clave)

    async def de_la_dlq() -> list[aio_pika.IncomingMessage]:
        mensajes = []
        while (m := await espia_dlq.get(no_ack=True, fail=False)) is not None:
            if (m.headers or {}).get("x-cola") == cola:
                mensajes.append(m)
        return mensajes

    yield type("Entorno", (), {"cola": cola, "consumidor": consumidor, "publicar": publicar, "dlq": de_la_dlq,
                               "canal": canal})
    for c in consumidores:
        await c.detener()
    for nombre in (cola, *(cola_de_reintento(cola, e) for e in ESPERAS)):
        await canal.queue_delete(nombre)
    if consumidores:  # broker de pruebas desechable: no se acumulan muertos entre corridas
        await (await canal.declare_queue("turismo.dead-letter", passive=True)).purge()


async def test_declara_la_cola_durable_con_salida_a_la_dlq(entorno, rabbitmq):
    """RabbitMQ acepta redeclarar una cola solo con los mismos argumentos: así se comprueba cómo quedó."""
    await entorno.consumidor(ManejadorFalso())
    await entorno.canal.declare_queue(entorno.cola, durable=True, arguments={"x-dead-letter-exchange": DLX})
    for espera in ESPERAS:
        await entorno.canal.declare_queue(cola_de_reintento(entorno.cola, espera), passive=True)
    otro_canal = await rabbitmq.channel()
    with pytest.raises(aio_pika.exceptions.ChannelPreconditionFailed):  # no es una cola temporal sin DLQ
        await otro_canal.declare_queue(entorno.cola, durable=False)


async def test_la_dlq_es_compatible_con_la_que_declara_catalog(entorno, rabbitmq):
    """Mismos argumentos que topologia_rabbitmq.py de catalog-service: si difirieran, el servicio
    que arrancara segundo recibiría PRECONDITION_FAILED y no podría consumir."""
    await entorno.consumidor(ManejadorFalso())
    canal = await rabbitmq.channel()
    dlx = await canal.declare_exchange("turismo.dlx", aio_pika.ExchangeType.TOPIC, durable=True)
    dlq = await canal.declare_queue("turismo.dead-letter", durable=True)
    await dlq.bind(dlx, routing_key="#")
    await canal.declare_exchange(rabbitmq.exchange_prueba, aio_pika.ExchangeType.TOPIC, durable=True)


async def test_un_mensaje_valido_se_procesa_y_se_reconoce(entorno):
    manejar = ManejadorFalso()
    await entorno.consumidor(manejar)
    sobre = servicio_publicado()
    await entorno.publicar(sobre)
    assert await hasta_que(lambda: _async(len(manejar.recibidos) == 1))
    await asyncio.sleep(0.2)
    assert manejar.recibidos == [sobre]  # una sola vez: el ack llegó y no se reentregó
    cola = await entorno.canal.declare_queue(entorno.cola, passive=True)
    assert cola.declaration_result.message_count == 0


async def test_un_fallo_pasajero_se_reintenta_y_luego_sale_bien(entorno):
    manejar = ManejadorFalso(fallos=2)
    await entorno.consumidor(manejar)
    await entorno.publicar(servicio_publicado())
    assert await hasta_que(lambda: _async(len(manejar.recibidos) == 3))  # 1 + 2 reintentos
    await asyncio.sleep(0.3)
    assert len(manejar.recibidos) == 3 and await entorno.dlq() == []


async def test_tras_tres_reintentos_va_a_la_dlq_con_el_error(entorno):
    manejar = ManejadorFalso(fallos=99)
    await entorno.consumidor(manejar)
    sobre = servicio_publicado()
    await entorno.publicar(sobre)
    assert await hasta_que(lambda: _async(len(manejar.recibidos) == 4), segundos=8)  # 1 + 3 reintentos
    muertos = []
    assert await hasta_que(lambda: _llenar(muertos, entorno.dlq))
    [m] = muertos
    assert json.loads(m.body) == sobre and m.message_id == sobre["event_id"]
    assert m.headers["x-intentos"] == 3 and m.headers["x-error"] == "ConnectionError: la base no responde"


@pytest.mark.parametrize("caso", ["json_roto", "error_permanente"])
async def test_un_mensaje_inservible_va_directo_a_la_dlq(entorno, caso):
    manejar = ManejadorFalso(fallos=99, error=ErrorPermanente("payload fuera de contrato"))
    await entorno.consumidor(manejar)
    await entorno.publicar(b"{no es json" if caso == "json_roto" else servicio_publicado())
    muertos = []
    assert await hasta_que(lambda: _llenar(muertos, entorno.dlq))
    assert muertos[0].headers["x-intentos"] == 0  # sin reintentos
    assert len(manejar.recibidos) == (0 if caso == "json_roto" else 1)


async def test_servicio_publicado_llega_a_servicio_ref_en_postgres(entorno, motor):
    """Camino real: RabbitMQ -> consumidor -> AplicarServicioPublicado -> Postgres."""
    ctx = Contexto(fabrica_postgres(fabrica_sesiones(motor)), RelojSistema())
    await entorno.consumidor(manejador_servicios(ctx))
    servicio_id = uuid.uuid4()

    async def version_guardada():
        async with motor.connect() as con:
            s = await RepositorioServiciosPostgres(con).leer(servicio_id)
        return s.version if s else None

    try:
        await entorno.publicar(servicio_publicado(version=2, servicio_id=servicio_id, tarifa_base=99000.5))
        assert await hasta_que(lambda: _igual(version_guardada, 2))
        await entorno.publicar(servicio_publicado(version=1, servicio_id=servicio_id))  # llega tarde: se descarta
        await asyncio.sleep(0.5)
        async with motor.connect() as con:
            s = await RepositorioServiciosPostgres(con).leer(servicio_id)
        assert s.version == 2 and s.tarifa_base == Decimal("99000.50")
        assert await entorno.dlq() == []
    finally:
        async with motor.begin() as con:
            await con.execute(delete(servicio_ref).where(servicio_ref.c.servicio_id == servicio_id))


async def test_la_app_declara_booking_servicios_al_arrancar(rabbitmq, rabbitmq_url, motor, base_migrada):
    """Mensajeria (lo que arranca main.py) declara la cola real y aplica lo que llega."""
    config = Configuracion(
        modo_persistencia="postgres", database_url=base_migrada,
        rabbitmq_url=rabbitmq_url, events_exchange=rabbitmq.exchange_prueba,
    )
    ctx = Contexto(fabrica_postgres(fabrica_sesiones(motor)), RelojSistema())
    mensajeria = Mensajeria(config, motor, ctx)
    mensajeria.iniciar()
    servicio_id = uuid.uuid4()
    canal = await rabbitmq.channel()
    try:
        async def existe_la_cola():
            try:
                await (await rabbitmq.channel()).declare_queue(COLA_SERVICIOS, passive=True)
                return True
            except aio_pika.exceptions.ChannelClosed:
                return False

        assert await hasta_que(existe_la_cola)
        await PublicadorRabbitMQ(rabbitmq, rabbitmq.exchange_prueba).publicar([servicio_publicado(servicio_id=servicio_id)])

        async def guardado():
            async with motor.connect() as con:
                return await RepositorioServiciosPostgres(con).leer(servicio_id) is not None

        assert await hasta_que(guardado)
    finally:
        await mensajeria.detener()
        async with motor.begin() as con:
            await con.execute(delete(servicio_ref).where(servicio_ref.c.servicio_id == servicio_id))
        limpieza = await conectar(rabbitmq_url)
        c = await limpieza.channel()
        for nombre in (COLA_SERVICIOS, *(cola_de_reintento(COLA_SERVICIOS, e) for e in (1.0, 5.0, 25.0))):
            await c.queue_delete(nombre)
        await limpieza.close()
        await canal.close()


async def _async(valor):
    return valor


async def _llenar(destino: list, fuente) -> bool:
    destino.extend(await fuente())
    return bool(destino)


async def _igual(funcion, esperado) -> bool:
    return await funcion() == esperado
