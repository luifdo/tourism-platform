import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_ok_con_postgres_real(database_url: str) -> None:
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "checks": {"database": "up"}}


def test_health_degradado_si_postgres_no_responde() -> None:
    # Puerto sin servidor: la sonda falla rápido y la réplica sale del enrutamiento.
    caida = "postgresql+asyncpg://nadie:nada@127.0.0.1:1/ninguna"
    with TestClient(create_app(Settings(database_url=caida))) as client:
        respuesta = client.get("/health")

    assert respuesta.status_code == 503
    assert respuesta.json() == {"status": "degraded", "checks": {"database": "down"}}


# La ruta no está en el contrato a propósito.
@pytest.mark.sin_contrato
def test_ruta_inexistente_responde_error_comun(database_url: str) -> None:
    with TestClient(create_app(Settings(database_url=database_url))) as client:
        respuesta = client.get("/no-existe", headers={"Accept-Language": "en"})

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "NO_ENCONTRADO"
    assert respuesta.headers["Content-Language"] == "en"
    assert respuesta.json()["correlation_id"] == respuesta.headers["X-Correlation-ID"]
