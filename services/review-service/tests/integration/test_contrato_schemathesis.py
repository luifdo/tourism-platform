"""Contrato REST con Schemathesis: peticiones generadas desde review.yaml contra la app real.

Complementa la validación de respuestas de tests/conftest.py (que revisa las peticiones que
escribimos a mano): aquí Schemathesis inventa cientos de peticiones válidas e inválidas por
operación (valores límite, textos raros, campos de más) y comprueba que el servicio:

* nunca responde 500;
* responde solo códigos, tipos de contenido y encabezados documentados, con el cuerpo según
  su esquema;
* rechaza lo que el contrato no permite y acepta lo que sí permite.

Corre con PostgreSQL real, como Turista, Prestador y Admin (las rutas de cada rol, y las
públicas con los tres). Los eventos que deje en el outbox los valida `engine`.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import schemathesis
import yaml
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings
from schemathesis.specs.openapi import checks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.main import create_app

pytestmark = pytest.mark.sin_contrato  # aquí juzga Schemathesis

CONTRATO = Path(__file__).resolve().parents[4] / "contracts" / "openapi" / "review.yaml"
BASE = "http://testserver/api/reviews"
ROLES = ("Turista", "Prestador", "Admin")

EXCLUIDAS = [
    # 405 y `Allow` los responde Starlette, no el contrato: si dos métodos de una ruta están
    # en routers distintos, solo anuncia el del primero.
    checks.unsupported_method,
    checks.allow_header_conformance,
    # Sin `If-Match` la API responde 428 Precondition Required (RFC 6585, documentado en el
    # contrato); Schemathesis solo acepta 400/401/403/406/415/422 para un encabezado faltante.
    checks.missing_required_header,
]
# Reglas que OpenAPI 3.0 no puede expresar (están en las descripciones del contrato). En estas
# operaciones Schemathesis arma peticiones que el esquema permite y la API rechaza con razón
# (400), así que no se exige que acepte todo lo "válido". En las demás, un 403/404/409 por
# elegibilidad, dueño o estado ya cuenta como respuesta aceptable para datos válidos.
# * responder: un texto solo con espacios cuenta como vacío;
# * reportar: `OTRO` exige `detalle`;
# * moderar: `OCULTAR` exige `motivo`.
CON_REGLAS_CRUZADAS = {
    "PUT /resenas/{resena_id}/respuesta",
    "POST /resenas/{resena_id}/reportes",
    "POST /resenas/{resena_id}/moderacion",
}


@pytest.fixture
async def usuarios(engine: AsyncEngine) -> dict[str, UUID]:
    """Un turista con una reseña y una visita pendiente, y el prestador dueño del servicio:
    sus rutas responden con datos y no solo con listas vacías."""
    turista, prestador, servicio, otro = uuid4(), uuid4(), uuid4(), uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO elegibilidad_resena VALUES (:t, :s, :v), (:t, :o, :v)"),
            {"t": turista, "s": servicio, "o": otro, "v": date(2026, 11, 14)},
        )
        await conn.execute(
            text("INSERT INTO servicio_dueno VALUES (:s, :p, 1)"), {"s": servicio, "p": prestador}
        )
        await conn.execute(
            text(
                "INSERT INTO resena (id, servicio_id, turista_id, puntuacion, ultima_visita,"
                " estado, creada_en) VALUES (:id, :s, :t, 4, :v, 'PUBLICADA', now())"
            ),
            {"id": uuid4(), "s": servicio, "t": turista, "v": date(2026, 11, 14)},
        )
    return {"Turista": turista, "Prestador": prestador, "Admin": uuid4()}


@pytest.fixture
def cliente(database_url: str, engine: AsyncEngine) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=database_url))
    with TestClient(app, raise_server_exceptions=False) as c:  # un 500 es un hallazgo
        yield c


def para_httpx(pedido: dict[str, Any]) -> dict[str, Any]:
    """Los argumentos de Schemathesis son de `requests`; httpx sube bytes crudos con `content`
    y ya no admite cookies por petición."""
    pedido = {k: v for k, v in pedido.items() if not (k == "cookies" and not v)}
    if isinstance(pedido.get("data"), bytes | str):
        pedido["content"] = pedido.pop("data")
    return pedido


@pytest.fixture
def contrato() -> Any:
    """El contrato tal como lo ve el servicio detrás de Traefik.

    * Sin `bearerAuth`: el JWT lo valida Traefik (ForwardAuth) y el servicio nunca recibe
      `Authorization`; autoriza por `X-Usuario-*` (sus 403 los prueban las pruebas e2e).
    * Sin `/health` ni `/metrics`: viven en la raíz (su propio `servers: /`), no bajo
      `/api/reviews`, y Schemathesis no aplica el `servers` de cada ruta.
    """
    datos = yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))
    datos.pop("security", None)
    datos["components"].pop("securitySchemes", None)
    for operaciones in datos["paths"].values():
        for operacion in operaciones.values():
            if isinstance(operacion, dict):
                operacion.pop("security", None)
    return schemathesis.openapi.from_dict(datos)


esquema = schemathesis.pytest.from_fixture("contrato").exclude(path_regex="^/(health|metrics)$")


@esquema.parametrize()
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_la_api_cumple_su_contrato(
    case: schemathesis.Case, cliente: TestClient, usuarios: dict[str, UUID]
) -> None:
    # Cada petición generada se manda con los tres roles (Schemathesis no admite parametrizar).
    for rol in ROLES:
        identidad = {"X-Usuario-Id": str(usuarios[rol]), "X-Usuario-Rol": rol}
        pedido = case.as_transport_kwargs(base_url=BASE, headers=identidad)
        respuesta = cliente.request(**para_httpx(pedido))
        excluidas = list(EXCLUIDAS)
        if f"{case.method} {case.path}" in CON_REGLAS_CRUZADAS:
            excluidas.append(checks.positive_data_acceptance)
        case.validate_response(respuesta, excluded_checks=excluidas, transport_kwargs=pedido)
