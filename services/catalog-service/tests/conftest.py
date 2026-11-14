"""Pruebas de contrato (Plan §8.3), activas en todas las pruebas.

Eventos: `validar_evento` comprueba un sobre contra contracts/events/ (envelope.v1 y el
esquema de su payload). La usan las pruebas de integración con los eventos que publican
(como lo haría el productor) y con los que deja el servicio en el outbox.

Contrato REST: toda respuesta que recibe una prueba se valida contra catalog.yaml.

Se intercepta `TestClient.send`, así que las pruebas unitarias y de integración que ya existen
validan el contrato sin escribir casos nuevos: código de respuesta documentado, tipo de
contenido, encabezados obligatorios y cuerpo según su esquema. Si algo no coincide, la prueba
falla con el detalle de qué campo no cumple.

Solo se validan respuestas: varias pruebas mandan a propósito peticiones inválidas (422).
Una prueba que de verdad necesite salirse del contrato usa `@pytest.mark.sin_contrato`.
"""

import json
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import pytest
import requests
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match
from openapi_core import Config, OpenAPI
from openapi_core.contrib.requests import RequestsOpenAPIRequest, RequestsOpenAPIResponse
from starlette.testclient import TestClient

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"
CONTRATO = CONTRATOS / "openapi" / "catalog.yaml"


@cache
def esquema_evento(nombre: str) -> Draft202012Validator:
    archivo = CONTRATOS / "events" / f"{nombre}.json"
    if not archivo.exists():
        raise AssertionError(f"No hay esquema en contracts/events/ para {nombre}")
    esquema = json.loads(archivo.read_text(encoding="utf-8"))
    return Draft202012Validator(esquema, format_checker=FormatChecker())


def validar_evento(sobre: dict[str, Any]) -> None:
    """Falla con el detalle si el sobre o su payload no cumplen contracts/events/."""
    errores = [f"sobre: {e.message}" for e in esquema_evento("envelope.v1").iter_errors(sobre)]
    if not errores:
        nombre = f"{sobre['event_type']}.v{sobre['version']}"
        errores = [
            f"payload.{'.'.join(map(str, e.path)) or '(raíz)'}: {e.message}"
            for e in esquema_evento(nombre).iter_errors(sobre["payload"])
        ]
    if errores:
        raise AssertionError(
            f"{sobre.get('event_type')} no cumple contracts/events/: " + "; ".join(errores)
        )


def _texto(valor: bytes | str, **_parametros: str) -> str:  # recibe el charset
    return valor.decode("utf-8-sig") if isinstance(valor, bytes) else valor.lstrip("﻿")


@cache
def contrato() -> OpenAPI:
    # El validador solo sabe leer JSON: GeoJSON (RFC 7946) es JSON y el CSV es texto.
    lectores = {"application/geo+json": json.loads, "text/csv": _texto}
    config = Config(extra_media_type_deserializers=lectores)
    return OpenAPI.from_path(CONTRATO, config=config)


def _como_requests(respuesta: httpx.Response) -> tuple[requests.PreparedRequest, requests.Response]:
    peticion = respuesta.request
    preparada = requests.Request(
        peticion.method, str(peticion.url), headers=dict(peticion.headers), data=peticion.content
    ).prepare()
    convertida = requests.Response()
    convertida.status_code = respuesta.status_code
    convertida.headers.update(respuesta.headers)
    convertida._content = respuesta.content
    convertida.url = str(peticion.url)
    return preparada, convertida


def validar_contra_contrato(respuesta: httpx.Response) -> None:
    peticion, convertida = _como_requests(respuesta)
    resultado = contrato().unmarshal_response(
        RequestsOpenAPIRequest(peticion), RequestsOpenAPIResponse(convertida)
    )
    if resultado.errors:
        detalle = "; ".join(_describir(e) for e in resultado.errors)
        raise AssertionError(
            f"{peticion.method} {respuesta.request.url.path} -> {respuesta.status_code} "
            f"no cumple catalog.yaml: {detalle}\nCuerpo: {respuesta.text[:500]}"
        )


def _describir(error: Exception) -> str:
    """Qué campo falla, con su ruta en el JSON (`items.0.zona: ...`), en vez del cuerpo entero."""
    causas = getattr(error.__cause__, "schema_errors", None) or getattr(error, "schema_errors", ())
    if not causas:
        return f"{type(error).__name__}: {error}"
    partes = []
    for causa in causas:
        hoja = best_match(causa.context) if causa.context else causa  # anyOf: la opción más cercana
        ruta = ".".join(map(str, hoja.absolute_path)) or "(raíz)"
        partes.append(f"{ruta}: {hoja.message}")
    return "; ".join(partes)


@pytest.fixture(name="validar_evento")
def fixture_validar_evento() -> Any:
    return validar_evento


@pytest.fixture(autouse=True)
def respuestas_segun_contrato(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker("sin_contrato"):
        yield
        return
    enviar = httpx.Client.send

    def enviar_y_validar(
        self: TestClient, peticion: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        respuesta = enviar(self, peticion, **kwargs)
        if not kwargs.get("stream"):
            validar_contra_contrato(respuesta)
        return respuesta

    monkeypatch.setattr(TestClient, "send", enviar_y_validar)
    yield
