"""Paso 5.2d: el repositorio de `solicitud_reserva` contra Postgres real."""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from application.errores import ReservaDuplicada
from application.ports import FiltroReservas
from domain.disponibilidad import DisponibilidadCupo
from domain.reglas import ZONA
from domain.reserva import Actor, EstadoReserva, Reserva
from domain.servicio import ServicioRef
from infrastructure.persistence.postgres import (
    RepositorioDisponibilidadPostgres,
    RepositorioReservasPostgres,
    RepositorioServiciosPostgres,
)
from infrastructure.persistence.tablas import disponibilidad_cupo, servicio_ref, solicitud_reserva

AHORA = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)
DIA_1, DIA_2, DIA_3 = date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)
VENCE = AHORA + timedelta(hours=48)  # expira_en de una solicitud hecha a las AHORA
ESPERA = 0.3


async def preparar(db) -> ServicioRef:
    """Un servicio con tres días abiertos (la reserva exige que el día exista: llave foránea)."""
    s = ServicioRef(uuid4(), uuid4(), uuid4(), 50, Decimal("50000"), True, 1)
    await RepositorioServiciosPostgres(db).guardar_si_mas_nuevo(s)
    for dia in (DIA_1, DIA_2, DIA_3):
        await RepositorioDisponibilidadPostgres(db).guardar(DisponibilidadCupo.abrir(s.servicio_id, dia, 50))
    return s


def nueva(s: ServicioRef, fecha: date = DIA_1, turista=None, minutos: int = 0, personas: int = 2) -> Reserva:
    return Reserva.solicitar(s, turista or uuid4(), fecha, personas, AHORA + timedelta(minutes=minutos))


# ---------- Una sola transacción (se deshace al final) ----------

@pytest.fixture
async def ctx(conexion):
    return RepositorioReservasPostgres(conexion), await preparar(conexion)


async def test_leer_una_que_no_existe_devuelve_none(ctx):
    repo, _ = ctx
    assert await repo.leer(uuid4()) is None
    assert await repo.obtener_para_cambiar(uuid4()) is None


async def test_guarda_una_nueva_y_la_lee_igual_con_hora_de_bogota(ctx):
    repo, s = ctx
    r = nueva(s)
    await repo.guardar(r)
    leida = await repo.leer(r.id)
    assert leida == r
    assert leida.expira_en.tzinfo == ZONA and leida.expira_en == VENCE


async def test_guarda_las_transiciones(ctx):
    repo, s = ctx
    r = nueva(s)
    await repo.guardar(r)
    r = await repo.obtener_para_cambiar(r.id)
    r.confirmar(AHORA + timedelta(hours=1))
    await repo.guardar(r)
    r = await repo.obtener_para_cambiar(r.id)
    r.cancelar(Actor.PRESTADOR, AHORA + timedelta(hours=2), motivo="Mal tiempo en el parque")
    await repo.guardar(r)
    leida = await repo.leer(r.id)
    assert (leida.estado, leida.cancelada_por, leida.motivo, leida.expira_en, leida.version) == (
        EstadoReserva.CANCELADA, Actor.PRESTADOR, "Mal tiempo en el parque", None, 3,
    )


async def test_guardar_sin_subir_la_version_es_un_error(ctx):
    repo, s = ctx
    r = nueva(s)
    await repo.guardar(r)
    with pytest.raises(RuntimeError, match="Escritura perdida"):
        await repo.guardar(r)


async def test_existe_activa(ctx):
    repo, s = ctx
    r = nueva(s)
    await repo.guardar(r)
    assert await repo.existe_activa(r.turista_id, s.servicio_id, DIA_1)
    assert not await repo.existe_activa(r.turista_id, s.servicio_id, DIA_1, excluir=r.id)
    assert not await repo.existe_activa(r.turista_id, s.servicio_id, DIA_2)
    r.cancelar(Actor.TURISTA, AHORA)
    await repo.guardar(r)
    assert not await repo.existe_activa(r.turista_id, s.servicio_id, DIA_1)  # cancelada ya no cuenta


async def test_el_indice_r6_se_traduce_a_reserva_duplicada(ctx):
    """Si dos activas iguales llegaran a guardarse (la segunda barrera), es un 409, no un 500."""
    repo, s = ctx
    turista = uuid4()
    await repo.guardar(nueva(s, turista=turista))
    with pytest.raises(ReservaDuplicada):
        await repo.guardar(nueva(s, turista=turista, minutos=1))


async def test_una_cancelada_no_impide_volver_a_reservar(ctx):
    repo, s = ctx
    turista = uuid4()
    r = nueva(s, turista=turista)
    r.cancelar(Actor.TURISTA, AHORA)
    await repo.guardar(r)
    await repo.guardar(nueva(s, turista=turista, minutos=1))  # el índice es parcial: solo activas


# ---------- listar ----------

@pytest.fixture
async def historial(ctx):
    """Un turista con 4 reservas (minutos 0..3) y una de otro turista."""
    repo, s = ctx
    turista = uuid4()
    rs = [nueva(s, fecha, turista, minutos=m) for m, fecha in enumerate((DIA_1, DIA_2, DIA_3))]
    rs[1].confirmar(AHORA + timedelta(hours=1))
    rs.append(nueva(s, DIA_1, uuid4(), minutos=10))  # de otro turista
    rs.append(nueva(s, DIA_2, uuid4(), minutos=20))  # de otro turista
    for r in rs:
        await repo.guardar(r)
    return repo, s, turista, rs


async def test_listar_historial_del_turista_mas_reciente_primero(historial):
    repo, _, turista, rs = historial
    pagina, total = await repo.listar(FiltroReservas(turista_id=turista), 1, 20)
    assert [r.id for r in pagina] == [rs[2].id, rs[1].id, rs[0].id] and total == 3


async def test_listar_filtra_por_estado_y_fechas(historial):
    repo, s, turista, rs = historial
    confirmadas, _ = await repo.listar(FiltroReservas(turista_id=turista, estado=EstadoReserva.CONFIRMADA), 1, 20)
    assert [r.id for r in confirmadas] == [rs[1].id]
    del_dia_1, _ = await repo.listar(FiltroReservas(servicio_id=s.servicio_id, desde=DIA_1, hasta=DIA_1), 1, 20)
    assert {r.id for r in del_dia_1} == {rs[0].id, rs[3].id}


async def test_listar_panel_del_prestador_lo_mas_urgente_primero(historial):
    """Por expira_en ascendente; las que ya no tienen plazo (confirmadas) van al final."""
    repo, s, _, rs = historial
    pagina, total = await repo.listar(
        FiltroReservas(prestador_usuario_id=s.prestador_usuario_id, orden="expira_en"), 1, 20
    )
    assert [r.id for r in pagina] == [rs[0].id, rs[2].id, rs[3].id, rs[4].id, rs[1].id] and total == 5


async def test_listar_pagina_con_el_total_y_sin_repetir(historial):
    repo, s, _, _ = historial
    filtro = FiltroReservas(prestador_usuario_id=s.prestador_usuario_id)
    p1, t1 = await repo.listar(filtro, 1, 2)
    p2, t2 = await repo.listar(filtro, 2, 2)
    p3, t3 = await repo.listar(filtro, 3, 2)
    vacia, t4 = await repo.listar(filtro, 9, 2)  # más allá de la última
    assert [len(p1), len(p2), len(p3), len(vacia)] == [2, 2, 1, 0]
    assert t1 == t2 == t3 == t4 == 5
    assert len({r.id for r in p1 + p2 + p3}) == 5


# ---------- Tareas programadas ----------

async def test_solicitudes_vencidas_solo_las_vencidas_en_orden(ctx):
    repo, s = ctx
    rs = [nueva(s, minutos=m) for m in (4, 0, 2, 30)]
    confirmada = nueva(s, minutos=1)
    confirmada.confirmar(AHORA + timedelta(minutes=5))
    for r in rs + [confirmada]:
        await repo.guardar(r)
    vencidas = await repo.solicitudes_vencidas(VENCE + timedelta(minutes=5), 10)
    assert [r.id for r in vencidas] == [rs[1].id, rs[2].id, rs[0].id]  # la del minuto 30 aún no vence
    assert len(await repo.solicitudes_vencidas(VENCE + timedelta(minutes=5), 2)) == 2  # respeta el límite


async def test_por_finalizar_solo_confirmadas_de_dias_pasados(ctx):
    repo, s = ctx
    rs = [nueva(s, fecha) for fecha in (DIA_1, DIA_2, DIA_1)]
    for r in rs[:2]:
        r.confirmar(AHORA + timedelta(hours=1))
    for r in rs:
        await repo.guardar(r)
    assert [r.id for r in await repo.por_finalizar(DIA_2, 10)] == [rs[0].id]  # la del 11 aún no; la 3.ª no está confirmada


# ---------- Varias transacciones a la vez (se confirman de verdad) ----------

@pytest.fixture
async def servicio_confirmado(motor):
    async with motor.begin() as con:
        s = await preparar(con)
    yield s
    async with motor.begin() as con:
        for tabla in (solicitud_reserva, disponibilidad_cupo, servicio_ref):
            await con.execute(delete(tabla).where(tabla.c.servicio_id == s.servicio_id))


async def test_quien_pide_una_reserva_bloqueada_espera_y_ve_el_cambio(motor, servicio_confirmado):
    """El prestador confirma mientras el turista cancela: el segundo ve lo que hizo el primero."""
    r = nueva(servicio_confirmado)
    async with motor.begin() as con:
        await RepositorioReservasPostgres(con).guardar(r)
    async with motor.connect() as t1, motor.connect() as t2:
        await t1.begin()
        await t2.begin()
        en_t1 = await RepositorioReservasPostgres(t1).obtener_para_cambiar(r.id)
        segundo = asyncio.create_task(RepositorioReservasPostgres(t2).obtener_para_cambiar(r.id))
        await asyncio.sleep(ESPERA)
        assert not segundo.done()
        en_t1.confirmar(AHORA + timedelta(hours=1))
        await RepositorioReservasPostgres(t1).guardar(en_t1)
        await t1.commit()
        assert (await asyncio.wait_for(segundo, 5)).estado is EstadoReserva.CONFIRMADA
        await t2.rollback()


async def test_dos_cronjobs_a_la_vez_no_toman_las_mismas_reservas(motor, servicio_confirmado):
    """SKIP LOCKED: el segundo no espera al primero; toma las que quedaron libres."""
    rs = [nueva(servicio_confirmado, minutos=m) for m in range(4)]
    async with motor.begin() as con:
        for r in rs:
            await RepositorioReservasPostgres(con).guardar(r)
    ahora = VENCE + timedelta(hours=1)
    async with motor.connect() as t1, motor.connect() as t2:
        await t1.begin()
        await t2.begin()
        lote_1 = await RepositorioReservasPostgres(t1).solicitudes_vencidas(ahora, 2)
        lote_2 = await asyncio.wait_for(RepositorioReservasPostgres(t2).solicitudes_vencidas(ahora, 10), ESPERA * 3)
        assert [r.id for r in lote_1] == [rs[0].id, rs[1].id]
        assert [r.id for r in lote_2] == [rs[2].id, rs[3].id]
        await t1.rollback()
        await t2.rollback()
