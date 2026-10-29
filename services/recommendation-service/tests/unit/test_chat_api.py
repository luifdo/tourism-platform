from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.responder_mensaje import ResponderMensaje
from src.infrastructure.http.dependencias import obtener_responder_mensaje
from src.main import app
from tests.contratos import validar
from tests.fakes import (
    HerramientasFalsas,
    ModeloCaido,
    ModeloGuionado,
    RegistroEnMemoria,
    SesionesEnMemoria,
    pedir,
    recomendacion,
    responder,
)

TURISTA = uuid4()
CAFE = uuid4()
IDENTIDAD = {"X-Usuario-Id": str(TURISTA), "X-Usuario-Rol": "Turista"}


def _cumple_el_contrato(respuesta) -> None:
    validar("recommendation.yaml", "/chat", respuesta.status_code, respuesta.json(), metodo="post")


@pytest.fixture
def chat_con():
    """Cliente cuyo chat usa el modelo indicado y dobles en memoria para lo demás."""

    def _crear(modelo: ModeloGuionado) -> tuple[TestClient, SesionesEnMemoria]:
        sesiones = SesionesEnMemoria()
        caso_de_uso = ResponderMensaje(
            modelo,
            HerramientasFalsas({"Tour de café": CAFE}),
            sesiones,
            RegistroEnMemoria(),
            reloj=lambda: datetime.now(UTC),
        )
        app.dependency_overrides[obtener_responder_mensaje] = lambda: caso_de_uso
        return TestClient(app), sesiones

    yield _crear
    app.dependency_overrides.clear()


def test_chat_responde_segun_el_contrato(chat_con):
    cliente, _ = chat_con(
        ModeloGuionado(
            pedir(("buscar_servicios", {"zona": "minca"})),
            responder(
                "Te recomiendo el tour de café.",
                recomendacion(CAFE, "Tour de café", "Minca tiene presión baja."),
            ),
        )
    )

    respuesta = cliente.post(
        "/api/recommendations/chat", json={"mensaje": "¿Qué hago en Minca?"}, headers=IDENTIDAD
    )

    assert respuesta.status_code == 200
    _cumple_el_contrato(respuesta)
    cuerpo = respuesta.json()
    assert cuerpo["respuesta"] == "Te recomiendo el tour de café."
    assert cuerpo["recomendaciones"] == [
        {
            "servicio_id": str(CAFE),
            "nombre": "Tour de café",
            "justificacion_explicabilidad": "Minca tiene presión baja.",
        }
    ]
    assert respuesta.headers["Content-Language"] == "es"


def test_continuar_la_conversacion(chat_con):
    cliente, sesiones = chat_con(ModeloGuionado(responder("Uno."), responder("Dos.")))
    primera = cliente.post("/api/recommendations/chat", json={"mensaje": "a"}, headers=IDENTIDAD)

    segunda = cliente.post(
        "/api/recommendations/chat",
        json={"mensaje": "b", "conversacion_id": primera.json()["conversacion_id"]},
        headers=IDENTIDAD,
    )

    assert segunda.status_code == 200
    assert segunda.json()["conversacion_id"] == primera.json()["conversacion_id"]
    [sesion] = sesiones.guardadas.values()
    assert len(sesion.mensajes) == 4


def test_responde_en_ingles_si_se_pide(chat_con):
    modelo = ModeloGuionado(responder("Hi!"))
    cliente, _ = chat_con(modelo)

    respuesta = cliente.post(
        "/api/recommendations/chat",
        json={"mensaje": "Hi"},
        headers=IDENTIDAD | {"Accept-Language": "en-US,en;q=0.9"},
    )

    assert respuesta.headers["Content-Language"] == "en"
    assert "inglés" in modelo.invocaciones[0].instrucciones


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"mensaje": ""},
        {"mensaje": "x" * 1001},
        {"mensaje": "hola", "conversacion_id": "no-es-uuid"},
    ],
)
def test_peticion_invalida(chat_con, cuerpo):
    cliente, _ = chat_con(ModeloGuionado())

    respuesta = cliente.post("/api/recommendations/chat", json=cuerpo, headers=IDENTIDAD)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "VALIDACION"
    _cumple_el_contrato(respuesta)


@pytest.mark.parametrize(
    "cabeceras",
    [
        {},
        {"X-Usuario-Id": str(TURISTA)},
        {"X-Usuario-Rol": "Turista"},
        {"X-Usuario-Id": "no-es-uuid", "X-Usuario-Rol": "Turista"},
    ],
)
def test_sin_identidad_valida(chat_con, cabeceras):
    cliente, _ = chat_con(ModeloGuionado())

    respuesta = cliente.post(
        "/api/recommendations/chat", json={"mensaje": "hola"}, headers=cabeceras
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "NO_AUTENTICADO"
    _cumple_el_contrato(respuesta)


def test_sin_identidad_responde_401_aunque_el_cuerpo_sea_invalido(chat_con):
    cliente, _ = chat_con(ModeloGuionado())

    respuesta = cliente.post("/api/recommendations/chat", json={})

    assert respuesta.status_code == 401


def test_un_rol_distinto_de_turista(chat_con):
    cliente, _ = chat_con(ModeloGuionado())

    respuesta = cliente.post(
        "/api/recommendations/chat",
        json={"mensaje": "hola"},
        headers={"X-Usuario-Id": str(TURISTA), "X-Usuario-Rol": "Prestador"},
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error"] == "PROHIBIDO"
    _cumple_el_contrato(respuesta)


def test_conversacion_no_encontrada(chat_con):
    cliente, _ = chat_con(ModeloGuionado())

    respuesta = cliente.post(
        "/api/recommendations/chat",
        json={"mensaje": "hola", "conversacion_id": str(uuid4())},
        headers=IDENTIDAD,
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "CONVERSACION_NO_ENCONTRADA"
    _cumple_el_contrato(respuesta)


def test_asistente_no_disponible_en_el_idioma_pedido(chat_con):
    cliente, _ = chat_con(ModeloCaido())

    respuesta = cliente.post(
        "/api/recommendations/chat",
        json={"mensaje": "hola"},
        headers=IDENTIDAD | {"Accept-Language": "en", "X-Correlation-Id": "abc-123"},
    )

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "ASISTENTE_NO_DISPONIBLE"
    assert "catalog" in cuerpo["message"]
    assert cuerpo["correlation_id"] == "abc-123"
    _cumple_el_contrato(respuesta)


def test_el_turista_del_cuerpo_se_ignora(chat_con):
    modelo = ModeloGuionado(pedir(("buscar_servicios", {})), responder("ok"))
    cliente, _ = chat_con(modelo)
    caso_de_uso = app.dependency_overrides[obtener_responder_mensaje]()

    cliente.post(
        "/api/recommendations/chat",
        json={"mensaje": "hola", "turista_id": str(uuid4())},
        headers=IDENTIDAD,
    )

    [(_, _, contexto)] = caso_de_uso._herramientas.ejecutadas
    assert contexto.turista_id == TURISTA


def test_sin_proveedor_configurado_el_chat_responde_503():
    # La app real, sin modelo inyectado: hasta la Fase 5 no hay proveedor.
    respuesta = TestClient(app).post(
        "/api/recommendations/chat", json={"mensaje": "hola"}, headers=IDENTIDAD
    )

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "ASISTENTE_NO_DISPONIBLE"
