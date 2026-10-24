"""Paso 5.3c: el manejador de servicio.publicado.v1 valida contra el contrato y aplica a servicio_ref."""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator

from application.base import Contexto
from domain.eventos import EventoDominio
from domain.reglas import ZONA
from infrastructure.messaging.consumidor import ErrorPermanente, manejador_servicios
from infrastructure.messaging.memoria import PublicadorMemoria
from infrastructure.messaging.sobre import armar_sobre
from infrastructure.persistence.memoria import AlmacenMemoria, fabrica_memoria
from infrastructure.reloj import RelojFijo

CONTRATO = Path(__file__).resolve().parents[4] / "contracts" / "events" / "servicio.publicado.v1.json"


def payload(**cambios):
    return {
        "servicio_id": str(uuid4()), "prestador_id": str(uuid4()), "prestador_usuario_id": str(uuid4()),
        "capacidad_aforo_diario": 20, "tarifa_base": 85000.5, "activo": True, "version": 1, **cambios,
    }


def sobre(datos, tipo="servicio.publicado"):
    return armar_sobre(EventoDominio(tipo, datos), None)


@pytest.fixture
def entorno():
    almacen = AlmacenMemoria()
    ctx = Contexto(fabrica_memoria(almacen, PublicadorMemoria()), RelojFijo(datetime(2026, 11, 1, tzinfo=ZONA)))
    return almacen, manejador_servicios(ctx)


def test_el_ejemplo_cumple_el_contrato_copiado_de_catalog():
    Draft202012Validator(json.loads(CONTRATO.read_text(encoding="utf-8"))).validate(payload())


async def test_aplica_un_servicio_nuevo(entorno):
    almacen, manejar = entorno
    datos = payload()
    assert await manejar(sobre(datos)) is True
    guardado = almacen.servicios[next(iter(almacen.servicios))]
    assert str(guardado.servicio_id) == datos["servicio_id"] and str(guardado.tarifa_base) == "85000.5"


async def test_un_repetido_o_viejo_se_descarta_sin_error(entorno):
    _, manejar = entorno
    datos = payload(version=2)
    assert await manejar(sobre(datos)) is True
    assert await manejar(sobre(datos)) is False  # repetido
    assert await manejar(sobre({**datos, "version": 1})) is False  # viejo


@pytest.mark.parametrize("malo", [
    pytest.param(lambda p: {k: v for k, v in p.items() if k != "activo"}, id="falta_un_campo"),
    pytest.param(lambda p: {**p, "extra": 1}, id="campo_de_mas"),
    pytest.param(lambda p: {**p, "servicio_id": "no-es-uuid"}, id="uuid_invalido"),
    pytest.param(lambda p: {**p, "capacidad_aforo_diario": 0}, id="aforo_cero"),
    pytest.param(lambda p: {**p, "tarifa_base": -1}, id="tarifa_negativa"),
    pytest.param(lambda p: None, id="sin_payload"),
])
async def test_un_payload_fuera_de_contrato_es_error_permanente(entorno, malo):
    almacen, manejar = entorno
    with pytest.raises(ErrorPermanente):
        await manejar(sobre(malo(payload())))
    assert not almacen.servicios


@pytest.mark.parametrize("cambio", [{"event_type": "reserva.solicitada"}, {"version": 2}], ids=["otro_tipo", "otra_version"])
async def test_un_sobre_de_otro_tipo_o_version_es_error_permanente(entorno, cambio):
    _, manejar = entorno
    with pytest.raises(ErrorPermanente):
        await manejar({**sobre(payload()), **cambio})
