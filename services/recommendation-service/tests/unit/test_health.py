import pytest
from fastapi.testclient import TestClient

from src.application.verificar_salud import VerificarSalud
from src.infrastructure.http.dependencias import obtener_verificar_salud
from src.main import app


class SondaFija:
    def __init__(self, responde: bool) -> None:
        self._responde = responde

    async def ping(self) -> bool:
        return self._responde


@pytest.fixture
def cliente_con():
    """Cliente cuyo /health ve PostgreSQL y Valkey como se le indique."""

    def _crear(base_de_datos: bool, valkey: bool) -> TestClient:
        salud = VerificarSalud(SondaFija(base_de_datos), SondaFija(valkey))
        app.dependency_overrides[obtener_verificar_salud] = lambda: salud
        return TestClient(app)

    yield _crear
    app.dependency_overrides.clear()


def test_health_responde_200_si_postgres_y_valkey_responden(cliente_con):
    respuesta = cliente_con(base_de_datos=True, valkey=True).get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "checks": {"database": "up", "valkey": "up"}}


@pytest.mark.parametrize(
    ("base_de_datos", "valkey"), [(False, True), (True, False), (False, False)]
)
def test_health_responde_503_si_alguna_dependencia_no_responde(cliente_con, base_de_datos, valkey):
    respuesta = cliente_con(base_de_datos=base_de_datos, valkey=valkey).get("/health")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "degraded"
    assert cuerpo["checks"] == {
        "database": "up" if base_de_datos else "down",
        "valkey": "up" if valkey else "down",
    }


def test_metrics_expone_formato_prometheus(cliente_con):
    cliente = cliente_con(base_de_datos=True, valkey=True)
    cliente.get("/health")

    respuesta = cliente.get("/metrics")

    assert respuesta.status_code == 200
    assert "http_requests_total" in respuesta.text
