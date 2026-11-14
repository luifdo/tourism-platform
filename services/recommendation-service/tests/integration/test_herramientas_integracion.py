"""Las 7 tools contra el contenedor mock-plataforma, por HTTP real.

Se omiten si el mock no responde. Para correrlas: `docker compose up -d mock-plataforma`.
"""

import os

import httpx
import pytest

from mocks.datos import SERVICIOS, TURISTA_CON_HISTORIAL
from src.application.ports.herramientas import ContextoTurista
from src.infrastructure.tools.herramientas_plataforma import HerramientasPlataforma

MOCK_URL = os.getenv("TEST_MOCK_URL", "http://localhost:9000")
CONTEXTO = ContextoTurista(turista_id=TURISTA_CON_HISTORIAL)
SERVICIO = str(SERVICIOS[1]["id"])


@pytest.fixture
async def herramientas():
    async with httpx.AsyncClient(timeout=5) as cliente:
        try:
            await cliente.get(f"{MOCK_URL}/health")
        except httpx.HTTPError:
            pytest.skip(f"mock-plataforma no responde en {MOCK_URL}")
        yield HerramientasPlataforma(
            cliente,
            f"{MOCK_URL}/api/catalog",
            f"{MOCK_URL}/api/bookings",
            f"{MOCK_URL}/api/reviews",
        )


@pytest.mark.parametrize(
    ("nombre", "argumentos", "clave"),
    [
        ("buscar_servicios", {"texto": "minca"}, "servicios"),
        ("detalle_servicio", {"servicio_id": SERVICIO}, "descripcion"),
        ("consultar_disponibilidad", {"servicio_id": SERVICIO, "desde": "2026-11-20"}, "dias"),
        ("historial_turista", {}, "reservas"),
        ("resenas_servicio", {"servicio_id": SERVICIO}, "recientes"),
        ("presion_capacidad_carga", {"zona": "minca"}, "zonas"),
        ("alertas_oficiales", {}, "alertas"),
    ],
)
async def test_cada_tool_responde_contra_el_mock(herramientas, nombre, argumentos, clave):
    resultado = await herramientas.ejecutar(nombre, argumentos, CONTEXTO)

    assert resultado.ok, resultado.datos
    assert resultado.datos[clave]


async def test_un_servicio_caido_da_un_error_controlado():
    async with httpx.AsyncClient(timeout=2) as cliente:
        herramientas = HerramientasPlataforma(
            cliente, "http://localhost:1/api/catalog", MOCK_URL, MOCK_URL
        )

        resultado = await herramientas.ejecutar("alertas_oficiales", {}, CONTEXTO)

    assert resultado.error == "SERVICIO_NO_DISPONIBLE"
