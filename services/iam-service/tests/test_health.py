from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_check_health
from app.application.use_cases.check_health import CheckHealth
from app.main import create_app


class FakeProbe:
    def __init__(self, up: bool) -> None:
        self._up = up

    async def ping(self) -> bool:
        return self._up


def make_client(database_up: bool = True, valkey_up: bool = True) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_check_health] = lambda: CheckHealth(
        database=FakeProbe(database_up), cache=FakeProbe(valkey_up)
    )
    return TestClient(app)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client() as c:
        yield c


def test_health_ok_con_postgresql_y_valkey(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "up", "valkey": "up"}}


@pytest.mark.parametrize(
    ("database_up", "valkey_up", "checks"),
    [
        (False, True, {"database": "down", "valkey": "up"}),
        (True, False, {"database": "up", "valkey": "down"}),
    ],
    ids=["postgresql_caido", "valkey_caido"],
)
def test_health_503_si_falla_una_dependencia(
    database_up: bool, valkey_up: bool, checks: dict[str, str]
) -> None:
    with make_client(database_up, valkey_up) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "checks": checks}


def test_health_live_no_consulta_dependencias() -> None:
    # Con PostgreSQL y Valkey caídos, la sonda de vida sigue en 200 (C-32).
    with make_client(database_up=False, valkey_up=False) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_exposed(client: TestClient) -> None:
    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
