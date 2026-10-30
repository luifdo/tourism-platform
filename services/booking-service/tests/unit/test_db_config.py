"""Paso 5.1a: configuración de la base y creación del motor (sin conectarse a Postgres)."""

import pytest
from pydantic import ValidationError

from config import Configuracion
from infrastructure.persistence.db import crear_motor, fabrica_sesiones, verificar_conexion


def test_por_defecto_sigue_en_modo_memoria():
    assert Configuracion().modo_persistencia == "memoria"


def test_un_modo_desconocido_se_rechaza():
    with pytest.raises(ValidationError):
        Configuracion(modo_persistencia="sqlite")


@pytest.mark.parametrize("url", ["postgresql://u:p@h/booking_db", "postgresql+psycopg2://u:p@h/booking_db", "sqlite:///x.db"])
def test_solo_acepta_el_driver_asincrono(url):
    with pytest.raises(ValidationError):
        Configuracion(database_url=url)


def test_lee_la_url_de_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://booking:secreto@postgres:5432/booking_db")
    assert Configuracion().database_url.endswith("@postgres:5432/booking_db")


async def test_el_motor_usa_asyncpg_y_el_pool_configurado():
    motor = crear_motor(Configuracion(db_pool_tamano=7, db_pool_extra=2))
    try:
        assert motor.dialect.driver == "asyncpg"
        assert motor.url.database == "booking_db"
        assert (motor.pool.size(), motor.pool._max_overflow) == (7, 2)
    finally:
        await motor.dispose()


async def test_crear_el_motor_no_abre_conexiones():
    motor = crear_motor(Configuracion())
    try:
        assert motor.pool.checkedout() == 0
        assert fabrica_sesiones(motor).kw["expire_on_commit"] is False
    finally:
        await motor.dispose()


async def test_verificar_conexion_devuelve_false_si_la_base_no_responde():
    # Puerto sin Postgres: la verificación no lanza, devuelve False (así /health puede responder 503).
    motor = crear_motor(Configuracion(database_url="postgresql+asyncpg://x:y@127.0.0.1:1/nada", db_pool_espera_s=1))
    try:
        assert await verificar_conexion(motor) is False
    finally:
        await motor.dispose()
