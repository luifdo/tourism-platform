"""Adaptador de Groq con el SDK real y la red simulada: no consume llamadas al proveedor."""

import json
import logging

import httpx
import pytest
from groq import AsyncGroq
from pydantic import SecretStr

from src.application.instrucciones import DECLARACION_RESPONDER
from src.application.ports.modelo_de_lenguaje import (
    LlamadaHerramienta,
    MensajeAsistente,
    MensajeTurista,
    ModeloNoDisponibleError,
    ResultadoLlamada,
)
from src.config import Configuracion
from src.infrastructure.llm.fabrica import SinProveedor, crear_modelo
from src.infrastructure.llm.modelo_groq import MODELO_POR_DEFECTO, ModeloGroq

CLAVE = "gsk_clave_de_prueba_que_no_debe_aparecer"


def _completion(contenido: str | None = None, llamadas: list[dict] | None = None) -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls" if llamadas else "stop",
                "message": {"role": "assistant", "content": contenido, "tool_calls": llamadas},
            }
        ],
    }


def _llamada(id_: str, nombre: str, argumentos: str) -> dict:
    return {"id": id_, "type": "function", "function": {"name": nombre, "arguments": argumentos}}


class Groq:
    """Transporte que responde como la API de Groq y guarda los cuerpos enviados."""

    def __init__(self, respuesta: httpx.Response | Exception) -> None:
        self.cuerpos: list[dict] = []
        self._respuesta = respuesta

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.cuerpos.append(json.loads(peticion.content))
        if isinstance(self._respuesta, Exception):
            raise self._respuesta
        return self._respuesta


def _modelo(groq_simulado: Groq, esfuerzo: str = "low") -> ModeloGroq:
    cliente = AsyncGroq(
        api_key=CLAVE,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(groq_simulado)),
    )
    return ModeloGroq(cliente, "openai/gpt-oss-120b", esfuerzo)


MENSAJES = [
    MensajeTurista("¿Qué hago en Minca?"),
    MensajeAsistente("", (LlamadaHerramienta("call_1", "buscar_servicios", {"zona": "minca"}),)),
    ResultadoLlamada("call_1", "buscar_servicios", {"origen": "x", "datos": {"total": 1}}),
    MensajeAsistente("Te recomiendo el tour."),
    MensajeTurista("¿Y en Taganga?"),
]


async def test_traduce_instrucciones_mensajes_y_tools_al_formato_de_groq():
    groq = Groq(httpx.Response(200, json=_completion("Hola")))

    await _modelo(groq).generar("INSTRUCCIONES", MENSAJES, [DECLARACION_RESPONDER])

    [cuerpo] = groq.cuerpos
    assert cuerpo["model"] == "openai/gpt-oss-120b"
    assert cuerpo["reasoning_effort"] == "low"
    assert cuerpo["tool_choice"] == "auto"
    assert [m["role"] for m in cuerpo["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert cuerpo["messages"][0]["content"] == "INSTRUCCIONES"
    pedido = cuerpo["messages"][2]
    assert pedido["tool_calls"][0]["id"] == "call_1"
    assert json.loads(pedido["tool_calls"][0]["function"]["arguments"]) == {"zona": "minca"}
    resultado = cuerpo["messages"][3]
    assert resultado["tool_call_id"] == "call_1"
    assert json.loads(resultado["content"]) == {"origen": "x", "datos": {"total": 1}}
    assert "tool_calls" not in cuerpo["messages"][4]
    [tool] = cuerpo["tools"]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "responder_al_turista"
    assert tool["function"]["parameters"]["required"] == ["respuesta", "recomendaciones"]


async def test_sin_esfuerzo_de_razonamiento_no_lo_envia():
    groq = Groq(httpx.Response(200, json=_completion("Hola")))

    await _modelo(groq, esfuerzo="").generar("x", [MensajeTurista("hola")], [])

    assert "reasoning_effort" not in groq.cuerpos[0]


async def test_lee_una_respuesta_de_texto():
    groq = Groq(httpx.Response(200, json=_completion("¡Hola! ¿En qué te ayudo?")))

    respuesta = await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert respuesta.texto == "¡Hola! ¿En qué te ayudo?"
    assert respuesta.llamadas == ()


async def test_lee_las_llamadas_a_tools():
    llamadas = [
        _llamada("call_a", "buscar_servicios", '{"zona": "minca", "categorias": ["CULTURA"]}'),
        _llamada("call_b", "alertas_oficiales", "{}"),
        _llamada("call_c", "detalle_servicio", "esto no es json"),
        _llamada("call_d", "detalle_servicio", '["una", "lista"]'),
    ]
    groq = Groq(httpx.Response(200, json=_completion(None, llamadas)))

    respuesta = await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert respuesta.texto == ""
    assert respuesta.llamadas == (
        LlamadaHerramienta(
            "call_a", "buscar_servicios", {"zona": "minca", "categorias": ["CULTURA"]}
        ),
        LlamadaHerramienta("call_b", "alertas_oficiales", {}),
        LlamadaHerramienta("call_c", "detalle_servicio", {}),
        LlamadaHerramienta("call_d", "detalle_servicio", {}),
    )


@pytest.mark.parametrize(
    "falla",
    [
        httpx.Response(
            401, json={"error": {"message": "Invalid API Key", "code": "invalid_api_key"}}
        ),
        httpx.Response(
            429, json={"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}}
        ),
        httpx.Response(500, json={"error": {"message": "Internal error"}}),
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(
            400, json={"error": {"message": "Failed to call a function", "code": "tool_use_failed"}}
        ),
        httpx.ConnectError("sin red"),
        httpx.ReadTimeout("tardó"),
    ],
)
async def test_las_fallas_de_groq_son_modelo_no_disponible(falla, caplog):
    caplog.set_level(logging.DEBUG)

    with pytest.raises(ModeloNoDisponibleError) as error:
        await _modelo(Groq(falla)).generar("x", [MensajeTurista("hola")], [])

    assert CLAVE not in str(error.value)
    assert CLAVE not in caplog.text


def test_nombre_para_el_registro():
    assert _modelo(Groq(httpx.Response(200))).nombre == "groq/openai/gpt-oss-120b"


# ---------- fábrica ----------


def test_la_fabrica_crea_groq_con_clave():
    modelo = crear_modelo(Configuracion(llm_provider="Groq", llm_api_key=SecretStr("gsk_x")))

    assert isinstance(modelo, ModeloGroq)
    assert modelo.nombre == f"groq/{MODELO_POR_DEFECTO}"


def test_la_fabrica_respeta_el_modelo_configurado():
    config = Configuracion(llm_provider="groq", llm_api_key=SecretStr("gsk_x"), llm_model="qwen/x")

    assert crear_modelo(config).nombre == "groq/qwen/x"


@pytest.mark.parametrize(
    "config",
    [
        Configuracion(),
        Configuracion(llm_provider="groq"),
        Configuracion(llm_provider="groq", llm_api_key=SecretStr("   ")),
        Configuracion(llm_provider="otro", llm_api_key=SecretStr("x")),
    ],
)
def test_sin_clave_o_con_proveedor_desconocido_no_hay_modelo(config):
    assert isinstance(crear_modelo(config), SinProveedor)


def test_la_clave_no_aparece_al_imprimir_la_configuracion():
    config = Configuracion(llm_provider="groq", llm_api_key=SecretStr(CLAVE))

    assert CLAVE not in repr(config)
    assert CLAVE not in str(config.model_dump())


class GroqEnSecuencia(Groq):
    """Responde en orden, una respuesta por petición."""

    def __init__(self, *respuestas: httpx.Response) -> None:
        super().__init__(httpx.Response(500))
        self._respuestas = list(respuestas)

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.cuerpos.append(json.loads(peticion.content))
        return self._respuestas.pop(0)


TOOL_USE_FAILED = httpx.Response(
    400,
    json={
        "error": {
            "message": "Failed to call a function.",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
            "failed_generation": '<|call|>buscar_servicios {"zona": minca}',
        }
    },
)


async def test_tool_use_failed_se_reintenta_una_vez(caplog):
    groq = GroqEnSecuencia(TOOL_USE_FAILED, httpx.Response(200, json=_completion("Listo")))

    respuesta = await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert respuesta.texto == "Listo"
    assert len(groq.cuerpos) == 2
    assert "buscar_servicios" in caplog.text


async def test_tool_use_failed_dos_veces_es_modelo_no_disponible():
    groq = GroqEnSecuencia(TOOL_USE_FAILED, TOOL_USE_FAILED)

    with pytest.raises(ModeloNoDisponibleError):
        await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert len(groq.cuerpos) == 2


async def test_otros_errores_no_se_reintentan():
    groq = GroqEnSecuencia(httpx.Response(401, json={"error": {"code": "invalid_api_key"}}))

    with pytest.raises(ModeloNoDisponibleError):
        await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert len(groq.cuerpos) == 1


async def test_groq_no_valida_por_su_cuenta_los_nombres_de_tools():
    groq = Groq(httpx.Response(200, json=_completion("Hola")))

    await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert groq.cuerpos[0]["disable_tool_validation"] is True


async def test_output_parse_failed_tambien_se_reintenta_una_vez():
    falla = httpx.Response(
        400, json={"error": {"message": "Parsing failed", "code": "output_parse_failed"}}
    )
    groq = GroqEnSecuencia(falla, httpx.Response(200, json=_completion("Listo")))

    respuesta = await _modelo(groq).generar("x", [MensajeTurista("hola")], [])

    assert respuesta.texto == "Listo"
    assert len(groq.cuerpos) == 2
