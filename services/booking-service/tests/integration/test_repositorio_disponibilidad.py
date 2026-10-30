"""Paso 5.2c: el repositorio de `disponibilidad_cupo` contra Postgres real, incluido el bloqueo FOR UPDATE."""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from application.errores import DiaExistente
from domain.disponibilidad import DisponibilidadCupo
from domain.servicio import ServicioRef
from infrastructure.persistence.postgres import RepositorioDisponibilidadPostgres, RepositorioServiciosPostgres
from infrastructure.persistence.tablas import disponibilidad_cupo, servicio_ref

DIA = date(2026, 11, 10)
ESPERA = 0.3  # segundos: tiempo de sobra para que una consulta que no está bloqueada termine


async def crear_servicio(db) -> ServicioRef:
    s = ServicioRef(uuid4(), uuid4(), uuid4(), 20, Decimal("50000"), True, 1)
    await RepositorioServiciosPostgres(db).guardar_si_mas_nuevo(s)
    return s


# ---------- Una sola transacción (se deshace al final) ----------

@pytest.fixture
async def repo_y_servicio(conexion):
    return RepositorioDisponibilidadPostgres(conexion), await crear_servicio(conexion)


async def test_un_dia_que_no_existe_devuelve_none(repo_y_servicio):
    repo, s = repo_y_servicio
    assert await repo.obtener_para_cambiar(s.servicio_id, DIA) is None


@pytest.mark.parametrize("tarifa", [Decimal("120000.50"), None], ids=["con_tarifa", "tarifa_base"])
async def test_guarda_un_dia_nuevo_y_lo_lee_igual(repo_y_servicio, tarifa):
    repo, s = repo_y_servicio
    dia = DisponibilidadCupo.abrir(s.servicio_id, DIA, 10, tarifa)
    await repo.guardar(dia)
    assert await repo.obtener_para_cambiar(s.servicio_id, DIA) == dia


async def test_guarda_los_cambios_de_un_dia_existente(repo_y_servicio):
    repo, s = repo_y_servicio
    await repo.guardar(DisponibilidadCupo.abrir(s.servicio_id, DIA, 10))
    dia = await repo.obtener_para_cambiar(s.servicio_id, DIA)
    dia.descontar(3)
    dia.ajustar(12, Decimal("70000"))
    await repo.guardar(dia)
    leido = await repo.obtener_para_cambiar(s.servicio_id, DIA)
    assert (leido.cupos_totales, leido.cupos_disponibles, leido.version, leido.secuencia) == (12, 9, 2, 3)


async def test_rango_devuelve_solo_ese_servicio_y_esas_fechas_en_orden(repo_y_servicio, conexion):
    repo, s = repo_y_servicio
    otro = await crear_servicio(conexion)
    for desfase in (3, 0, 1, 5):  # se guardan en desorden
        await repo.guardar(DisponibilidadCupo.abrir(s.servicio_id, DIA + timedelta(days=desfase), 10))
    await repo.guardar(DisponibilidadCupo.abrir(otro.servicio_id, DIA, 10))
    dias = await repo.rango(s.servicio_id, DIA, DIA + timedelta(days=3))
    assert [d.fecha for d in dias] == [DIA, DIA + timedelta(days=1), DIA + timedelta(days=3)]


async def test_postgres_rechaza_mas_disponibles_que_totales(repo_y_servicio):
    """La segunda barrera: aunque el dominio fallara, el CHECK de la tabla no deja guardarlo."""
    repo, s = repo_y_servicio
    await repo.guardar(DisponibilidadCupo.abrir(s.servicio_id, DIA, 10))
    with pytest.raises(IntegrityError, match="disponibles_en_rango"):
        await repo.guardar(DisponibilidadCupo(s.servicio_id, DIA, 10, 11, secuencia=2))


async def test_guardar_un_dia_sin_subir_la_secuencia_es_un_error(repo_y_servicio):
    """Señal de que alguien lo modificó sin bloquearlo: falla fuerte en vez de perder una escritura."""
    repo, s = repo_y_servicio
    dia = DisponibilidadCupo.abrir(s.servicio_id, DIA, 10)
    dia.descontar(1)
    await repo.guardar(dia)
    with pytest.raises(RuntimeError, match="Escritura perdida"):
        await repo.guardar(dia)  # misma secuencia (2) que la guardada


# ---------- Varias transacciones a la vez (se confirman de verdad) ----------

@pytest.fixture
async def servicio_confirmado(motor):
    async with motor.begin() as con:
        s = await crear_servicio(con)
    yield s
    async with motor.begin() as con:
        await con.execute(delete(disponibilidad_cupo).where(disponibilidad_cupo.c.servicio_id == s.servicio_id))
        await con.execute(delete(servicio_ref).where(servicio_ref.c.servicio_id == s.servicio_id))


@pytest.fixture
async def dia_confirmado(motor, servicio_confirmado) -> DisponibilidadCupo:
    dia = DisponibilidadCupo.abrir(servicio_confirmado.servicio_id, DIA, 1)  # un solo cupo
    async with motor.begin() as con:
        await RepositorioDisponibilidadPostgres(con).guardar(dia)
    return dia


async def test_quien_pide_un_dia_bloqueado_espera_y_luego_ve_el_valor_nuevo(motor, dia_confirmado):
    """Dos turistas por el último cupo: el segundo espera al primero y ya no lo encuentra."""
    sid = dia_confirmado.servicio_id
    async with motor.connect() as t1, motor.connect() as t2:
        await t1.begin()
        await t2.begin()
        dia_t1 = await RepositorioDisponibilidadPostgres(t1).obtener_para_cambiar(sid, DIA)

        segundo = asyncio.create_task(RepositorioDisponibilidadPostgres(t2).obtener_para_cambiar(sid, DIA))
        await asyncio.sleep(ESPERA)
        assert not segundo.done()  # está esperando el bloqueo de t1

        dia_t1.descontar(1)
        await RepositorioDisponibilidadPostgres(t1).guardar(dia_t1)
        await t1.commit()

        dia_t2 = await asyncio.wait_for(segundo, 5)
        assert dia_t2.cupos_disponibles == 0  # no lee el 1 de antes: lee lo que t1 confirmó
        await t2.rollback()


async def test_consultar_el_rango_no_espera_a_quien_tiene_el_dia_bloqueado(motor, dia_confirmado):
    sid = dia_confirmado.servicio_id
    async with motor.connect() as t1, motor.connect() as t2:
        await t1.begin()
        await RepositorioDisponibilidadPostgres(t1).obtener_para_cambiar(sid, DIA)
        dias = await asyncio.wait_for(RepositorioDisponibilidadPostgres(t2).rango(sid, DIA, DIA), ESPERA * 3)
        assert [d.cupos_disponibles for d in dias] == [1]
        await t1.rollback()


async def test_dos_peticiones_que_crean_el_mismo_dia_a_la_vez_no_se_pisan(motor, servicio_confirmado):
    """Un día nuevo no tiene fila que bloquear: la segunda creación recibe DiaExistente."""
    sid = servicio_confirmado.servicio_id
    async with motor.connect() as t1, motor.connect() as t2:
        await t1.begin()
        await t2.begin()
        await RepositorioDisponibilidadPostgres(t1).guardar(DisponibilidadCupo.abrir(sid, DIA, 10))

        segundo = asyncio.create_task(
            RepositorioDisponibilidadPostgres(t2).guardar(DisponibilidadCupo.abrir(sid, DIA, 4))
        )
        await asyncio.sleep(ESPERA)
        assert not segundo.done()  # espera a ver si t1 confirma o deshace
        await t1.commit()

        with pytest.raises(DiaExistente):
            await asyncio.wait_for(segundo, 5)
        await t2.rollback()

    async with motor.connect() as con:
        assert [d.cupos_totales for d in await RepositorioDisponibilidadPostgres(con).rango(sid, DIA, DIA)] == [10]
