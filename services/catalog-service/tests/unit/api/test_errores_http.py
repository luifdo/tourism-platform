"""Los errores que responde el propio FastAPI/Starlette salen con el formato común `Error`.

Lo encontró Schemathesis: un cuerpo que no es JSON respondía `{"detail": ...}`, solo en
inglés y sin `correlation_id`, fuera del contrato.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PRESTADOR = {
    "X-Usuario-Id": "7ff7f887-4cf0-4dc9-b38f-a097b5594639",
    "X-Usuario-Rol": "Prestador",
    "Content-Type": "application/json",
}


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def formato_comun(cuerpo: dict) -> bool:
    return set(cuerpo) == {"error", "message", "correlation_id"} and bool(cuerpo["correlation_id"])


def test_cuerpo_que_no_es_json(cliente: TestClient) -> None:
    r = cliente.post("/api/catalog/servicios", content=b'{"nombre": ', headers=PRESTADOR)
    assert r.status_code == 400
    assert formato_comun(r.json()) and r.json()["error"] == "VALIDACION"


@pytest.mark.sin_contrato  # la ruta no existe: no está en el contrato
def test_ruta_que_no_existe_en_ingles(cliente: TestClient) -> None:
    r = cliente.get("/api/catalog/no-existe", headers={"Accept-Language": "en"})
    assert r.status_code == 404
    assert formato_comun(r.json()) and r.json()["error"] == "NO_ENCONTRADO"
    assert r.json()["message"].startswith("The requested resource")


@pytest.mark.sin_contrato  # DELETE /zonas no está en el contrato
def test_metodo_no_admitido_conserva_allow(cliente: TestClient) -> None:
    r = cliente.delete("/api/catalog/zonas")
    assert r.status_code == 405
    assert formato_comun(r.json()) and r.json()["error"] == "METODO_NO_PERMITIDO"
    assert "DELETE" in r.json()["message"]
    assert "GET" in r.headers["allow"]
