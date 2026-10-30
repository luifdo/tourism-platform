"""Idempotencia en un Valkey real (python scripts/valkey_pruebas.py subir).

Lo importante: la reserva de la clave es atómica entre procesos, y dos réplicas de la API que
comparten Valkey no crean dos reservas con la misma Idempotency-Key.
"""

import asyncio
import os
from datetime import datetime
from uuid import uuid4

import httpx
import pytest

from application.errores import IdempotenciaNoDisponible
from application.ports import RespuestaGuardada
from config import Configuracion
from domain.reglas import ZONA
from infrastructure.http import demo
from infrastructure.persistence.idempotencia_valkey import TTL_SEGUNDOS, AlmacenIdempotenciaValkey, crear_cliente
from infrastructure.reloj import RelojFijo
from main import contenedor_postgres, crear_app

AHORA = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)  # el mismo reloj de la fixture `cliente`
VALKEY_URL = os.environ.get("TEST_VALKEY_URL", "redis://127.0.0.1:6380/0")
BASE = "/api/bookings"
TURISTA = {"X-Usuario-Id": str(demo.USUARIO_TURISTA_DEMO), "X-Usuario-Rol": "Turista"}


async def test_de_veinte_peticiones_simultaneas_solo_una_reserva_la_clave(valkey):
    almacen = AlmacenIdempotenciaValkey(valkey)
    clave = f"{valkey.prefijo}k"
    resultados = await asyncio.gather(*(almacen.reservar(clave) for _ in range(20)))
    assert resultados.count(True) == 1
    assert await almacen.obtener(clave) is None  # en proceso


async def test_la_respuesta_se_guarda_48_horas_y_vuelve_igual(valkey):
    almacen = AlmacenIdempotenciaValkey(valkey)
    clave = f"{valkey.prefijo}k"
    respuesta = RespuestaGuardada(201, '{"id": "r1", "ciudad": "Santa Marta"}'.encode(), {"etag": '"1"'})
    await almacen.reservar(clave)
    await almacen.guardar(clave, respuesta)
    assert await almacen.obtener(clave) == respuesta
    assert TTL_SEGUNDOS - 60 < await valkey.ttl(clave) <= TTL_SEGUNDOS


async def test_liberar_y_vencimiento_de_la_marca(valkey):
    almacen = AlmacenIdempotenciaValkey(valkey, ttl_en_proceso=1)
    clave = f"{valkey.prefijo}k"
    await almacen.reservar(clave)
    await almacen.liberar(clave)
    assert await almacen.reservar(clave) is True
    await asyncio.sleep(1.5)  # el pod "murió" sin liberar: Valkey borra la marca solo
    assert await almacen.reservar(clave) is True


async def test_si_valkey_no_responde_no_se_ejecuta_nada():
    cliente = crear_cliente("redis://127.0.0.1:1/0")
    try:
        with pytest.raises(IdempotenciaNoDisponible):
            await AlmacenIdempotenciaValkey(cliente).reservar("k")
    finally:
        await cliente.aclose()


async def test_dos_replicas_no_crean_dos_reservas_con_la_misma_clave(cliente, valkey, base_migrada):
    """`cliente` es la réplica A; se arma una réplica B con su propio proceso lógico (otro
    contenedor, otro pool) contra la misma booking_db y el mismo Valkey."""
    config = Configuracion(
        modo_persistencia="postgres", database_url=base_migrada, valkey_url=VALKEY_URL, datos_demo=False
    )
    contenedor_b = contenedor_postgres(config, RelojFijo(AHORA))
    replica_b = crear_app(config, contenedor_b)
    cuerpo = {"servicio_id": str(demo.SERVICIO_DEMO), "fecha_reserva": "2026-11-10", "numero_personas": 2}
    clave = {"Idempotency-Key": str(uuid4())}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=replica_b), base_url="http://b") as b:
            primera = await cliente.post(BASE, json=cuerpo, headers={**TURISTA, **clave})
            reintento = await b.post(BASE, json=cuerpo, headers={**TURISTA, **clave})
    finally:
        await contenedor_b.extras["motor"].dispose()
        await contenedor_b.extras["valkey"].aclose()

    assert primera.status_code == reintento.status_code == 201
    assert reintento.json()["id"] == primera.json()["id"]
    assert reintento.headers["ETag"] == primera.headers["ETag"]
    assert (await cliente.get(f"{BASE}/mis-reservas", headers=TURISTA)).json()["total"] == 1
