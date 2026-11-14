"""Contrato REST con Schemathesis: peticiones generadas desde catalog.yaml contra la app real.

Complementa la validación de respuestas de tests/conftest.py (que revisa las peticiones que
escribimos a mano): aquí Schemathesis inventa cientos de peticiones válidas e inválidas por
operación (valores límite, textos raros, campos de más) y comprueba que el servicio:

* nunca responde 500;
* responde solo códigos, tipos de contenido y encabezados documentados, con el cuerpo según
  su esquema;
* rechaza lo que el contrato no permite y acepta lo que sí permite.

Corre con PostgreSQL, Valkey y RabbitMQ reales, como Entidad y como Prestador (las rutas de
cada rol, y las públicas con ambos). Los eventos que deje en el outbox los valida `engine`.
"""

from collections.abc import Iterator
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
from valkey import Valkey

from app.api.dependencies import get_geocodificador
from app.application.dto.candidato_direccion import CandidatoDireccion
from app.config import get_settings
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.persistence.database import build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.sin_contrato]  # aquí juzga Schemathesis

CONTRATO = Path(__file__).resolve().parents[4] / "contracts" / "openapi" / "catalog.yaml"
BASE = "http://testserver/api/catalog"
ROLES = ("Entidad", "Prestador")

EXCLUIDAS = [
    # 405 y `Allow` los responde Starlette, no el contrato: si GET y POST de una ruta están en
    # routers distintos, solo anuncia el método del primero.
    checks.unsupported_method,
    checks.allow_header_conformance,
    # Sin `If-Match` la API responde 428 Precondition Required (RFC 6585, documentado en el
    # contrato); Schemathesis solo acepta 400/401/403/406/415/422 para un encabezado faltante.
    checks.missing_required_header,
]
# Reglas entre campos que OpenAPI 3.0 no puede expresar (están en las descripciones del
# contrato). En estas operaciones Schemathesis arma combinaciones que el esquema permite y la
# API rechaza con razón (400), así que no se exige que acepte todo lo "válido":
# * búsqueda: `orden=relevancia` requiere `texto`; `orden=distancia`, `lat` y `lon`;
# * mapas: en `bbox` cada mínimo menor que su máximo;
# * servicios: el bloque de `atributos` que corresponde depende del `tipo`;
# * zonas: el polígono debe estar cerrado y ser válido (sin cruces);
# * alertas: exactamente uno de `servicio_id` o `zona`, y vencimiento futuro (hasta 365 días);
# * rangos de fechas: `desde` <= `hasta`, como máximo 366 días;
# * servicio y perfil: un campo de más responde 400 (no se puede declarar en el contrato porque
#   esos esquemas se reutilizan con `allOf` en la respuesta editable).
CON_REGLAS_CRUZADAS = {
    "GET /buscar",
    "GET /mapa/servicios",
    "GET /mapa/zonas",
    "GET /mapa/alertas",
    "GET /analitica/mapa-calor",
    "POST /servicios",
    "PUT /servicios/{servicio_id}",
    "POST /zonas",
    "PUT /zonas/{zona_id}",
    "POST /alertas",
    "PUT /alertas/{alerta_id}",
    "GET /prestador/metricas",
    "PUT /prestador/perfil",
    "GET /analitica/demanda",
    "GET /analitica/intenciones-visita",
    "GET /analitica/tablero",
    "GET /analitica/reportes/demanda",
}


class GeocodificadorFalso:
    """Sin llamar a Nominatim desde las pruebas."""

    async def buscar(self, direccion: str, idioma: Idioma) -> list[CandidatoDireccion]:
        return [CandidatoDireccion(Coordenada(lat=11.24, lon=-74.21), direccion)]


@pytest.fixture
async def usuario_prestador(engine: AsyncEngine) -> UUID:
    """Prestador aprobado: sus rutas responden con datos y no con 404 por perfil."""
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Turismo Sierra")
    async with SqlUnidadDeTrabajo(build_session_factory(engine)) as uow:
        await uow.prestadores.guardar(perfil)
        await uow.confirmar()
    return perfil.usuario_id


@pytest.fixture
async def zonas_iniciales(engine: AsyncEngine) -> Any:
    """Al terminar borra las zonas que haya creado Schemathesis (las demás pruebas cuentan
    las seis iniciales)."""
    async with engine.connect() as conn:
        antes = set(await conn.scalars(text("SELECT id FROM zona")))
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM zona WHERE NOT (id = ANY(:ids))"), {"ids": list(antes)}
        )


@pytest.fixture
def cliente(
    database_url: str, valkey_url: str, engine: AsyncEngine, zonas_iniciales: Any
) -> Iterator[TestClient]:
    configuracion = get_settings().model_copy(
        update={
            "database_url": database_url,
            "valkey_url": valkey_url,
            "s3_access_key": "prueba",
            "s3_secret_key": "prueba",
        }
    )
    app = create_app(configuracion)
    app.dependency_overrides[get_geocodificador] = GeocodificadorFalso
    with TestClient(app, raise_server_exceptions=False) as c:  # un 500 es un hallazgo
        yield c
    # Las búsquedas que hizo quedan en caché: la base se limpia, Valkey no.
    Valkey.from_url(valkey_url).flushdb()


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
      `/api/catalog`, y Schemathesis no aplica el `servers` de cada ruta.
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
    case: schemathesis.Case, cliente: TestClient, usuario_prestador: UUID
) -> None:
    # Cada petición generada se manda con los dos roles (Schemathesis no admite parametrizar).
    for rol in ROLES:
        identidad = {
            "X-Usuario-Id": str(usuario_prestador if rol == "Prestador" else uuid4()),
            "X-Usuario-Rol": rol,
        }
        pedido = case.as_transport_kwargs(base_url=BASE, headers=identidad)
        respuesta = cliente.request(**para_httpx(pedido))
        excluidas = list(EXCLUIDAS)
        if f"{case.method} {case.path}" in CON_REGLAS_CRUZADAS:
            excluidas.append(checks.positive_data_acceptance)
        case.validate_response(respuesta, excluded_checks=excluidas, transport_kwargs=pedido)
