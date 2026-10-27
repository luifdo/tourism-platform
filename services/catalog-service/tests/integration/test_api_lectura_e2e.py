"""La API de lectura completa: HTTP → caso de uso → PostGIS, sin dobles."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente(database_url: str, engine: object) -> Iterator[TestClient]:
    # `engine` limpia las tablas al terminar; Valkey apunta a un puerto cerrado: sin caché.
    settings = get_settings().model_copy(
        update={"database_url": database_url, "valkey_url": "redis://127.0.0.1:1/0"}
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_zonas_iniciales_en_ambos_idiomas(cliente: TestClient) -> None:
    es = cliente.get("/api/catalog/zonas").json()
    en = cliente.get("/api/catalog/zonas", headers={"Accept-Language": "en"}).json()
    assert "Parque Nacional Natural Tayrona" in [z["nombre"] for z in es]
    assert "Tayrona National Natural Park" in [z["nombre"] for z in en]


def test_busqueda_vacia_y_servicio_inexistente(cliente: TestClient) -> None:
    r = cliente.get(
        "/api/catalog/buscar", params={"lat": 11.24, "lon": -74.21, "orden": "distancia"}
    )
    assert r.status_code == 200 and r.json()["total"] == 0
    r = cliente.get("/api/catalog/servicios/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["error"] == "NO_ENCONTRADO"


def test_health_y_metricas(cliente: TestClient) -> None:
    assert cliente.get("/health").json() == {"status": "ok", "checks": {"database": "up"}}
    assert "http_requests_total" in cliente.get("/metrics").text


def test_mapa_de_zonas_en_geojson(cliente: TestClient) -> None:
    r = cliente.get(
        "/api/catalog/mapa/zonas",
        params={"zoom": 12, "bbox": "-74.25,11.20,-74.15,11.30"},
        headers={"Accept-Language": "en"},
    )
    assert r.status_code == 200 and r.headers["content-type"] == "application/geo+json"
    nombres = {f["properties"]["nombre"] for f in r.json()["features"]}
    assert "Historic Center" in nombres and "Minca" not in nombres
    r = cliente.get("/api/catalog/mapa/servicios", params={"zoom": 10, "bbox": "-75,11,-73,12"})
    assert r.json() == {"type": "FeatureCollection", "features": []}
