"""Una conversación de punta a punta con PostgreSQL, Valkey y el mock-plataforma reales.

Solo el modelo de lenguaje es un doble con guion. Se omite si falta alguna dependencia:
`docker compose up -d postgres valkey mock-plataforma`.
"""

import os

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from mocks.datos import SERVICIOS, TURISTA_CON_HISTORIAL
from src.application.ports.modelo_de_lenguaje import ResultadoLlamada
from src.config import Configuracion
from src.main import create_app
from tests.contratos import validar
from tests.fakes import ModeloGuionado, pedir, recomendacion, responder

MOCK_URL = os.getenv("TEST_MOCK_URL", "http://localhost:9000")
IDENTIDAD = {"X-Usuario-Id": str(TURISTA_CON_HISTORIAL), "X-Usuario-Rol": "Turista"}
CAFE = SERVICIOS[1]


@pytest.fixture
async def config(motor, valkey, urls_reales):
    async with httpx.AsyncClient(timeout=2) as cliente:
        try:
            await cliente.get(f"{MOCK_URL}/health")
        except httpx.HTTPError:
            pytest.skip(f"mock-plataforma no responde en {MOCK_URL}")
    db_url, valkey_url = urls_reales
    return Configuracion(
        db_url=db_url,
        valkey_url=valkey_url,
        catalog_url=f"{MOCK_URL}/api/catalog",
        booking_url=f"{MOCK_URL}/api/bookings",
        review_url=f"{MOCK_URL}/api/reviews",
    )


def _ve_el_cafe(mensajes) -> object:
    """Paso del guion que comprueba que el resultado real de la tool llegó al modelo."""
    [busqueda] = [
        m for m in mensajes if isinstance(m, ResultadoLlamada) and m.nombre == "buscar_servicios"
    ]
    nombres = [s["nombre"] for s in busqueda.contenido["datos"]["servicios"]]
    assert CAFE["nombre"] in nombres
    return responder(
        "Te recomiendo el tour de café en Minca.",
        recomendacion(CAFE["id"], CAFE["nombre"], "Minca tiene presión de capacidad baja."),
    )


async def test_conversacion_completa(config, motor, valkey):
    modelo = ModeloGuionado(
        pedir(
            ("buscar_servicios", {"zona": "minca"}), ("presion_capacidad_carga", {"zona": "minca"})
        ),
        _ve_el_cafe,
        pedir(("historial_turista", {})),
        responder("Ya reservaste buceo en Taganga para el 8 de noviembre."),
    )
    app = create_app(config, modelo=modelo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cliente:
        primera = await cliente.post(
            "/api/recommendations/chat", json={"mensaje": "¿Qué hago en Minca?"}, headers=IDENTIDAD
        )
        conversacion_id = primera.json()["conversacion_id"]
        segunda = await cliente.post(
            "/api/recommendations/chat",
            json={"mensaje": "¿Y qué tengo reservado?", "conversacion_id": conversacion_id},
            headers=IDENTIDAD,
        )

    assert primera.status_code == 200, primera.text
    validar("recommendation.yaml", "/chat", 200, primera.json(), metodo="post")
    assert [r["servicio_id"] for r in primera.json()["recomendaciones"]] == [str(CAFE["id"])]

    # La segunda petición conserva el contexto de la primera.
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["conversacion_id"] == conversacion_id
    historial = [type(m).__name__ for m in modelo.invocaciones[3].mensajes[:3]]
    assert historial == ["MensajeTurista", "MensajeAsistente", "MensajeTurista"]

    # Quedó una fila en recomendacion_log por la recomendación, sin texto de la conversación.
    async with motor.connect() as conexion:
        filas = (
            (
                await conexion.execute(
                    text("SELECT * FROM recomendacion_log WHERE conversacion_id = :id"),
                    {"id": conversacion_id},
                )
            )
            .mappings()
            .all()
        )
    [fila] = filas
    assert fila["servicio_id"] == CAFE["id"]
    assert fila["turista_id"] == TURISTA_CON_HISTORIAL
    assert fila["herramientas_usadas"] == ["buscar_servicios", "presion_capacidad_carga"]
    assert fila["modelo"] == "pruebas/guion"
    assert "Minca" not in " ".join(str(v) for k, v in fila.items() if k != "justificacion")

    # Y la sesión quedó en Valkey con los 4 mensajes.
    sesion = await valkey.get(f"recommendation:conversacion:{conversacion_id}")
    assert sesion is not None
    assert b"tengo reservado" in sesion
