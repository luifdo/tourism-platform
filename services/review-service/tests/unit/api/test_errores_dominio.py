"""Cada error del dominio tiene estado HTTP y mensaje en los dos idiomas."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errores.manejador_errores import ESTADO_POR_CODIGO, registrar_manejadores
from app.api.i18n.mensajes_error import MENSAJES
from app.domain import errors
from app.domain.errors import DemasiadosReportes, ErrorDominio, VersionDistinta
from app.domain.value_objects.idioma import Idioma

CODIGOS = sorted(
    c.codigo
    for c in vars(errors).values()
    if isinstance(c, type) and issubclass(c, ErrorDominio) and c is not ErrorDominio
)


@pytest.mark.parametrize("codigo", CODIGOS)
def test_codigo_con_estado_y_mensajes(codigo: str) -> None:
    assert codigo in ESTADO_POR_CODIGO
    if codigo != "VALIDACION":  # su texto sale de la regla incumplida
        assert set(MENSAJES[codigo]) == set(Idioma)


def cliente_que_lanza(error: ErrorDominio) -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)

    @app.get("/x")
    async def lanzar() -> None:
        raise error

    return TestClient(app)


# Rutas de prueba fuera del contrato.
@pytest.mark.sin_contrato
def test_demasiados_reportes_responde_429_con_retry_after() -> None:
    respuesta = cliente_que_lanza(DemasiadosReportes(retry_after=600, limite=10)).get(
        "/x", headers={"Accept-Language": "en"}
    )
    assert respuesta.status_code == 429
    assert respuesta.headers["Retry-After"] == "600"
    assert respuesta.json()["message"] == (
        "You reached the limit of 10 reports per hour. Try again in 600 seconds."
    )


@pytest.mark.sin_contrato
def test_version_distinta_responde_409_con_etag() -> None:
    respuesta = cliente_que_lanza(VersionDistinta(version_actual=4)).get("/x")
    assert respuesta.status_code == 409
    assert respuesta.headers["ETag"] == '"4"'
