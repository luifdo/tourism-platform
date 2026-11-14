"""Prueba manual con Groq real (Fase 5). Consume cuota: no corre con `pytest` a secas.

    docker compose up -d postgres valkey mock-plataforma
    uv run pytest -m groq -s

Lee LLM_API_KEY y LLM_MODEL de .env. Son pocas conversaciones a propósito.
"""

from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text

from mocks.datos import SERVICIOS, TURISTA_CON_HISTORIAL
from src.config import Configuracion
from src.main import create_app

pytestmark = pytest.mark.groq

MOCK_URL = "http://localhost:9000"
IDS_DEL_MOCK = {s["id"] for s in SERVICIOS}


def _env() -> dict[str, str]:
    ruta = Path(__file__).parents[2] / ".env"
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    return dict(
        linea.split("=", 1) for linea in lineas if "=" in linea and not linea.startswith("#")
    )


@pytest.fixture
async def config(motor, valkey, urls_reales):
    env = _env()
    if not env.get("LLM_API_KEY", "").strip():
        pytest.skip("Falta LLM_API_KEY en .env")
    async with httpx.AsyncClient(timeout=2) as cliente:
        try:
            await cliente.get(f"{MOCK_URL}/health")
        except httpx.HTTPError:
            pytest.skip("mock-plataforma no responde")
    db_url, valkey_url = urls_reales
    return Configuracion(
        db_url=db_url,
        valkey_url=valkey_url,
        catalog_url=f"{MOCK_URL}/api/catalog",
        booking_url=f"{MOCK_URL}/api/bookings",
        review_url=f"{MOCK_URL}/api/reviews",
        llm_provider="groq",
        llm_api_key=SecretStr(env["LLM_API_KEY"].strip()),
        llm_model=env.get("LLM_MODEL", "").strip(),
    )


async def _chat(app, mensaje: str, idioma: str = "es") -> httpx.Response:
    cabeceras = {
        "X-Usuario-Id": str(TURISTA_CON_HISTORIAL),
        "X-Usuario-Rol": "Turista",
        "Accept-Language": idioma,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cliente:
        return await cliente.post(
            "/api/recommendations/chat", json={"mensaje": mensaje}, headers=cabeceras, timeout=90
        )


def _mostrar(respuesta: httpx.Response) -> None:
    cuerpo = respuesta.json()
    print(f"\n[{respuesta.status_code}] {cuerpo.get('respuesta') or cuerpo}")
    for r in cuerpo.get("recomendaciones", []):
        print(f"  - {r['nombre']}: {r['justificacion_explicabilidad']}")


async def test_conversacion_real_en_espanol(config, motor):
    respuesta = await _chat(
        create_app(config),
        "Quiero un plan tranquilo de naturaleza para el 20 de noviembre. ¿Qué me recomiendas?",
    )
    _mostrar(respuesta)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["respuesta"].strip()
    recomendados = {UUID(r["servicio_id"]) for r in cuerpo["recomendaciones"]}
    # Nunca un servicio inventado: todos salieron del catálogo (el mock).
    assert recomendados <= IDS_DEL_MOCK
    async with motor.connect() as conexion:
        filas = (
            await conexion.execute(
                text("SELECT modelo FROM recomendacion_log WHERE conversacion_id = :id"),
                {"id": cuerpo["conversacion_id"]},
            )
        ).all()
    assert len(filas) == len(recomendados)
    assert all(f.modelo.startswith("groq/") for f in filas)


async def test_conversacion_real_en_ingles(config):
    respuesta = await _chat(create_app(config), "What can I do in Palomino?", idioma="en")
    _mostrar(respuesta)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["Content-Language"] == "en"
    assert {UUID(r["servicio_id"]) for r in respuesta.json()["recomendaciones"]} <= IDS_DEL_MOCK


async def test_clave_invalida_da_503_y_el_servicio_sigue_sano(config):
    # Groq rechaza la clave antes de procesar nada: no consume cuota.
    app = create_app(config.model_copy(update={"llm_api_key": SecretStr(f"gsk_{uuid4().hex}")}))

    respuesta = await _chat(app, "Hola")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cliente:
        salud = await cliente.get("/health")

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "ASISTENTE_NO_DISPONIBLE"
    assert salud.status_code == 200
