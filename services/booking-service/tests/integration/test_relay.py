"""Paso 5.3b: el relay del outbox contra Postgres real, con un publicador falso.

(La publicación real en RabbitMQ se prueba en test_rabbitmq.py.)
"""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from domain.eventos import EventoDominio
from infrastructure.messaging.relay import RelayOutbox
from infrastructure.persistence.postgres import OutboxPostgres
from infrastructure.persistence.tablas import evento_outbox


class PublicadorFalso:
    def __init__(self, falla_en: set[int] = frozenset(), demora_s: float = 0):
        self.publicados: list[dict] = []
        self._falla_en = set(falla_en)  # números de llamada (1, 2, ...) que fallan
        self._llamadas = 0
        self._demora_s = demora_s

    async def publicar(self, sobres):
        self._llamadas += 1
        await asyncio.sleep(self._demora_s)
        if self._llamadas in self._falla_en:
            raise ConnectionError("RabbitMQ no confirmó")
        self.publicados.extend(sobres)

    def numeros(self) -> list[int]:
        return [s["payload"]["n"] for s in self.publicados]


@pytest.fixture
async def outbox_vacio(motor):
    async with motor.begin() as con:
        await con.execute(delete(evento_outbox))
    yield
    async with motor.begin() as con:
        await con.execute(delete(evento_outbox))


async def agregar(motor, cuantos: int, transacciones: int = 1) -> None:
    """`cuantos` eventos numerados 0..cuantos-1, repartidos en varias transacciones."""
    por_tx = cuantos // transacciones
    for t in range(transacciones):
        async with motor.begin() as con:
            await OutboxPostgres(con).agregar(
                [EventoDominio("auditoria.registrada", {"n": n}) for n in range(t * por_tx, (t + 1) * por_tx)], None
            )


async def filas(motor):
    async with motor.connect() as con:
        return (await con.execute(select(evento_outbox).order_by(evento_outbox.c.creado_en))).mappings().all()


async def test_publica_los_pendientes_en_orden_y_los_marca(motor, outbox_vacio):
    await agregar(motor, 6, transacciones=3)
    publicador = PublicadorFalso()
    assert await RelayOutbox(motor, publicador).una_vuelta() == 6
    assert publicador.numeros() == [0, 1, 2, 3, 4, 5]
    assert all(f["publicado_en"] is not None for f in await filas(motor))
    assert await RelayOutbox(motor, publicador).una_vuelta() == 0  # nada pendiente: no repite
    assert len(publicador.publicados) == 6


async def test_el_sobre_publicado_es_el_guardado(motor, outbox_vacio):
    await agregar(motor, 1)
    publicador = PublicadorFalso()
    await RelayOutbox(motor, publicador).una_vuelta()
    [fila] = await filas(motor)
    assert publicador.publicados == [fila["sobre"]] and UUID(publicador.publicados[0]["event_id"]) == fila["id"]


async def test_respeta_el_tamano_del_lote(motor, outbox_vacio):
    await agregar(motor, 5)
    publicador = PublicadorFalso()
    relay = RelayOutbox(motor, publicador, lote=2)
    assert [await relay.una_vuelta() for _ in range(4)] == [2, 2, 1, 0]
    assert publicador.numeros() == [0, 1, 2, 3, 4]


async def test_si_uno_falla_cuenta_el_intento_y_los_siguientes_esperan(motor, outbox_vacio):
    await agregar(motor, 4)
    publicador = PublicadorFalso(falla_en={2})  # falla el segundo evento
    assert await RelayOutbox(motor, publicador).una_vuelta() == 1

    estado = [(f["publicado_en"] is not None, f["intentos"], f["ultimo_error"]) for f in await filas(motor)]
    assert estado == [
        (True, 0, None),
        (False, 1, "ConnectionError: RabbitMQ no confirmó"),
        (False, 0, None),  # no se adelantó al que falló
        (False, 0, None),
    ]
    assert await RelayOutbox(motor, publicador).una_vuelta() == 3  # RabbitMQ volvió
    assert publicador.numeros() == [0, 1, 2, 3]  # nada se perdió y el orden se mantuvo


async def test_dos_relays_a_la_vez_no_publican_dos_veces(motor, outbox_vacio):
    """Dos réplicas: SKIP LOCKED reparte los eventos; cada uno sale exactamente una vez."""
    await agregar(motor, 40, transacciones=4)
    publicador = PublicadorFalso(demora_s=0.005)  # lento, para que las vueltas se crucen
    relays = [RelayOutbox(motor, publicador, lote=10) for _ in range(2)]

    async def vaciar(relay):
        while await relay.una_vuelta():
            pass

    await asyncio.gather(*(vaciar(r) for r in relays))
    assert sorted(publicador.numeros()) == list(range(40))  # sin duplicados ni faltantes


async def test_correr_publica_lo_nuevo_y_para_cuando_se_le_pide(motor, outbox_vacio):
    publicador = PublicadorFalso()
    parar = asyncio.Event()
    tarea = asyncio.create_task(RelayOutbox(motor, publicador).correr(parar, espera_s=0.05))
    await agregar(motor, 3)
    for _ in range(100):  # hasta 5 s
        if len(publicador.publicados) == 3:
            break
        await asyncio.sleep(0.05)
    parar.set()
    await asyncio.wait_for(tarea, 2)
    assert publicador.numeros() == [0, 1, 2]


async def test_correr_sobrevive_a_un_error_de_la_base(outbox_vacio):
    """Si la base no responde, la vuelta falla, se registra y el relay sigue vivo."""
    sin_base = create_async_engine("postgresql+asyncpg://booking:booking@127.0.0.1:1/booking_db")
    parar = asyncio.Event()
    tarea = asyncio.create_task(RelayOutbox(sin_base, PublicadorFalso()).correr(parar, espera_s=0.01))
    await asyncio.sleep(0.3)
    assert not tarea.done()  # no murió con la excepción
    parar.set()
    await asyncio.wait_for(tarea, 2)
    await sin_base.dispose()
