"""Paso 5.1c: la migración 0001 contra Postgres real, y que sus restricciones de verdad protegen los datos."""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import IntegrityError

from domain.reglas import ZONA
from infrastructure.persistence.tablas import disponibilidad_cupo, metadata, servicio_ref, solicitud_reserva

FECHA = date(2026, 11, 10)


# ---------- La migración ----------

async def test_crea_las_cuatro_tablas(conexion):
    filas = await conexion.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    ))
    assert [f[0] for f in filas] == ["alembic_version", "disponibilidad_cupo", "evento_outbox", "servicio_ref", "solicitud_reserva"]


async def test_la_base_migrada_coincide_con_tablas_py(conexion):
    """Si alguien cambia tablas.py y olvida la migración (o al revés), esta prueba lo detecta."""
    diferencias = await conexion.run_sync(lambda con: compare_metadata(MigrationContext.configure(con), metadata))
    assert diferencias == []


def test_baja_y_vuelve_a_subir(alembic_cfg):
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


# ---------- Las restricciones protegen los datos ----------

async def crear_servicio(conexion) -> dict:
    servicio = {
        "servicio_id": uuid4(), "prestador_id": uuid4(), "prestador_usuario_id": uuid4(),
        "capacidad_aforo_diario": 20, "tarifa_base": 85000, "activo": True, "version": 1,
    }
    await conexion.execute(insert(servicio_ref).values(servicio))
    return servicio


async def abrir_dia(conexion, servicio: dict, totales: int = 10, fecha: date = FECHA) -> None:
    await conexion.execute(insert(disponibilidad_cupo).values(
        servicio_id=servicio["servicio_id"], fecha=fecha, cupos_totales=totales, cupos_disponibles=totales,
    ))


def reserva(servicio: dict, turista_id=None, **cambios) -> dict:
    ahora = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)
    fila = {
        "id": uuid4(), "turista_id": turista_id or uuid4(), "servicio_id": servicio["servicio_id"],
        "prestador_id": servicio["prestador_id"], "prestador_usuario_id": servicio["prestador_usuario_id"],
        "fecha_reserva": FECHA, "numero_personas": 2, "estado": "SOLICITADA",
        "expira_en": ahora + timedelta(hours=48), "creado_en": ahora, "actualizado_en": ahora,
    }
    return {**fila, **cambios}


async def debe_rechazar(conexion, sentencia, restriccion: str) -> None:
    """Ejecuta en un savepoint, así un fallo esperado no aborta la transacción de la prueba."""
    with pytest.raises(IntegrityError) as error:
        async with conexion.begin_nested():
            await conexion.execute(sentencia)
    assert restriccion in str(error.value)


async def test_postgres_no_deja_mas_disponibles_que_totales(conexion):
    servicio = await crear_servicio(conexion)
    await abrir_dia(conexion, servicio, totales=10)
    sentencia = update(disponibilidad_cupo).where(disponibilidad_cupo.c.fecha == FECHA).values(cupos_disponibles=11)
    await debe_rechazar(conexion, sentencia, "ck_disponibilidad_cupo_disponibles_en_rango")


async def test_postgres_no_deja_cupos_negativos(conexion):
    servicio = await crear_servicio(conexion)
    await abrir_dia(conexion, servicio, totales=1)
    sentencia = update(disponibilidad_cupo).values(cupos_disponibles=disponibilidad_cupo.c.cupos_disponibles - 2)
    await debe_rechazar(conexion, sentencia, "ck_disponibilidad_cupo_disponibles_en_rango")


async def test_no_se_abre_un_dia_de_un_servicio_desconocido(conexion):
    sentencia = insert(disponibilidad_cupo).values(servicio_id=uuid4(), fecha=FECHA, cupos_totales=5, cupos_disponibles=5)
    await debe_rechazar(conexion, sentencia, "fk_disponibilidad_cupo_servicio_id")


async def test_no_se_reserva_un_dia_que_no_esta_abierto(conexion):
    servicio = await crear_servicio(conexion)
    sentencia = insert(solicitud_reserva).values(reserva(servicio))
    await debe_rechazar(conexion, sentencia, "fk_solicitud_reserva_dia")


async def test_r6_una_sola_reserva_activa_por_turista_servicio_y_fecha(conexion):
    servicio = await crear_servicio(conexion)
    await abrir_dia(conexion, servicio)
    turista = uuid4()
    await conexion.execute(insert(solicitud_reserva).values(reserva(servicio, turista)))
    await debe_rechazar(conexion, insert(solicitud_reserva).values(reserva(servicio, turista)), "uq_solicitud_reserva_activa")


async def test_r6_permite_reservar_de_nuevo_si_la_anterior_se_cancelo(conexion):
    servicio = await crear_servicio(conexion)
    await abrir_dia(conexion, servicio)
    turista = uuid4()
    cancelada = reserva(servicio, turista, estado="CANCELADA", expira_en=None, cancelada_por="Turista")
    await conexion.execute(insert(solicitud_reserva).values(cancelada))
    await conexion.execute(insert(solicitud_reserva).values(reserva(servicio, turista)))  # no falla
    total = await conexion.scalar(select(text("count(*)")).select_from(solicitud_reserva))
    assert total == 2


@pytest.mark.parametrize(
    ("cambios", "restriccion"),
    [
        ({"estado": "CONFIRMDA"}, "ck_solicitud_reserva_estado_valido"),
        ({"estado": "CONFIRMADA"}, "ck_solicitud_reserva_plazo_solo_en_solicitada"),  # confirmada con plazo
        ({"expira_en": None}, "ck_solicitud_reserva_plazo_solo_en_solicitada"),  # solicitada sin plazo
        ({"estado": "RECHAZADA", "expira_en": None}, "ck_solicitud_reserva_rechazo_con_motivo"),
        ({"estado": "CANCELADA", "expira_en": None}, "ck_solicitud_reserva_cancelada_por_solo_en_cancelada"),
        ({"cancelada_por": "Admin"}, "ck_solicitud_reserva_cancelada_por"),
        ({"numero_personas": 0}, "ck_solicitud_reserva_personas_positivas"),
    ],
    ids=["estado_mal_escrito", "confirmada_con_plazo", "solicitada_sin_plazo", "rechazo_sin_motivo",
         "cancelada_sin_quien", "cancelada_por_invalido", "cero_personas"],
)
async def test_postgres_rechaza_reservas_incoherentes(conexion, cambios, restriccion):
    servicio = await crear_servicio(conexion)
    await abrir_dia(conexion, servicio)
    await debe_rechazar(conexion, insert(solicitud_reserva).values(reserva(servicio, **cambios)), restriccion)


async def test_el_dinero_se_guarda_exacto(conexion):
    servicio = await crear_servicio(conexion)
    await conexion.execute(
        update(servicio_ref).where(servicio_ref.c.servicio_id == servicio["servicio_id"]).values(tarifa_base="0.30")
    )
    guardada = await conexion.scalar(select(servicio_ref.c.tarifa_base).where(servicio_ref.c.servicio_id == servicio["servicio_id"]))
    assert str(guardada) == "0.30"
