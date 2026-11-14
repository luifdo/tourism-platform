from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_check_health
from app.application.use_cases.check_health import CheckHealth
from app.main import create_app


class FakeDatabaseProbe:
    def __init__(self, up: bool) -> None:
        self._up = up

    async def ping(self) -> bool:
        return self._up


def make_client(database_up: bool) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_check_health] = lambda: CheckHealth(
        database=FakeDatabaseProbe(database_up)
    )
    return TestClient(app)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client(database_up=True) as c:
        yield c


def test_health_ok_when_database_is_up(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "up"}}


def test_health_degraded_when_database_is_down() -> None:
    with make_client(database_up=False) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "checks": {"database": "down"}}


def test_metrics_exposed(client: TestClient) -> None:
    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
