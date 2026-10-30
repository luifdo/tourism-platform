"""Adaptador de Groq (ADR-011): traduce nuestro formato al de `chat.completions` y viceversa."""

import json
import logging
from collections.abc import Sequence
from typing import Any

import groq
from groq import AsyncGroq

from src.application.ports.herramientas import DeclaracionHerramienta
from src.application.ports.modelo_de_lenguaje import (
    LlamadaHerramienta,
    MensajeAsistente,
    MensajeModelo,
    MensajeTurista,
    ModeloNoDisponibleError,
    RespuestaModelo,
    ResultadoLlamada,
)

logger = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "openai/gpt-oss-120b"
# Groq responde 400 con estos códigos cuando no logra leer lo que generó el modelo (la
# llamada a tool o la salida). La generación varía, así que un reintento suele salir bien.
FALLAS_DE_LECTURA = {"tool_use_failed", "output_parse_failed"}
REINTENTOS_FALLA_DE_LECTURA = 1


class ModeloGroq:
    """Implementa ModeloDeLenguaje con la API de Groq. Nunca registra la clave."""

    def __init__(
        self,
        cliente: AsyncGroq,
        modelo: str = MODELO_POR_DEFECTO,
        esfuerzo_razonamiento: str = "",
        # Groq descuenta este máximo de la cuota por minuto al recibir la petición, aunque
        # no se use: las respuestas reales rondan 50-250 tokens.
        max_tokens: int = 1024,
    ) -> None:
        self._cliente = cliente
        self._modelo = modelo
        self._esfuerzo_razonamiento = esfuerzo_razonamiento
        self._max_tokens = max_tokens

    @property
    def nombre(self) -> str:
        return f"groq/{self._modelo}"

    async def generar(
        self,
        instrucciones: str,
        mensajes: Sequence[MensajeModelo],
        herramientas: Sequence[DeclaracionHerramienta],
    ) -> RespuestaModelo:
        peticion: dict[str, Any] = {
            "model": self._modelo,
            "messages": [{"role": "system", "content": instrucciones}, *map(_mensaje, mensajes)],
            "tools": [_tool(h) for h in herramientas],
            "tool_choice": "auto",
            # Una tool desconocida no corta la petición: la rechaza nuestro servicio y el
            # modelo recibe HERRAMIENTA_DESCONOCIDA para corregirse.
            "disable_tool_validation": True,
            "temperature": 0.2,
            "max_completion_tokens": self._max_tokens,
        }
        if self._esfuerzo_razonamiento:
            # Menos razonamiento = menos tokens y menos latencia (solo modelos que lo admiten).
            peticion["reasoning_effort"] = self._esfuerzo_razonamiento

        for intento in range(1 + REINTENTOS_FALLA_DE_LECTURA):
            try:
                respuesta = await self._cliente.chat.completions.create(**peticion)
                break
            except groq.APIStatusError as exc:
                codigo = _codigo(exc)
                if codigo in FALLAS_DE_LECTURA and intento < REINTENTOS_FALLA_DE_LECTURA:
                    # La generación varía: un nuevo intento suele producir una llamada válida.
                    logger.warning(
                        "Groq no pudo leer lo que generó el modelo (%s); se reintenta. "
                        "Generado: %.300r",
                        codigo,
                        _generacion_fallida(exc),
                    )
                    continue
                # 401 clave inválida, 429 límite, 5xx caído: para el turista, todo es
                # "el asistente no está disponible". El cuerpo no lleva la clave.
                logger.warning("Groq respondió %s: %s", exc.status_code, codigo)
                raise ModeloNoDisponibleError(f"Groq respondió {exc.status_code}") from exc
            except (groq.APIConnectionError, groq.APIError) as exc:
                logger.warning("No se pudo hablar con Groq: %s", type(exc).__name__)
                raise ModeloNoDisponibleError("Groq no responde") from exc

        if respuesta.usage is not None:
            # Para vigilar la cuota (el plan gratuito limita los tokens por minuto).
            logger.info(
                "Groq %s: %s tokens (%s de entrada, %s de salida)",
                self._modelo,
                respuesta.usage.total_tokens,
                respuesta.usage.prompt_tokens,
                respuesta.usage.completion_tokens,
            )
        mensaje = respuesta.choices[0].message
        llamadas = tuple(
            LlamadaHerramienta(
                id=llamada.id,
                nombre=llamada.function.name,
                argumentos=_argumentos(llamada.function.arguments),
            )
            for llamada in mensaje.tool_calls or []
        )
        return RespuestaModelo(texto=mensaje.content or "", llamadas=llamadas)

    async def cerrar(self) -> None:
        await self._cliente.close()


def crear_modelo_groq(
    api_key: str, modelo: str, esfuerzo_razonamiento: str, timeout_segundos: float
) -> ModeloGroq:
    # Un solo reintento: los reintentos también consumen la cuota del proveedor.
    cliente = AsyncGroq(api_key=api_key, timeout=timeout_segundos, max_retries=1)
    return ModeloGroq(cliente, modelo or MODELO_POR_DEFECTO, esfuerzo_razonamiento)


def _tool(declaracion: DeclaracionHerramienta) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": declaracion.nombre,
            "description": declaracion.descripcion,
            "parameters": declaracion.parametros,
        },
    }


def _mensaje(mensaje: MensajeModelo) -> dict[str, Any]:
    match mensaje:
        case MensajeTurista(texto=texto):
            return {"role": "user", "content": texto}
        case MensajeAsistente(texto=texto, llamadas=()):
            return {"role": "assistant", "content": texto}
        case MensajeAsistente(texto=texto, llamadas=llamadas):
            return {
                "role": "assistant",
                "content": texto or None,
                "tool_calls": [
                    {
                        "id": ll.id,
                        "type": "function",
                        "function": {
                            "name": ll.nombre,
                            "arguments": json.dumps(ll.argumentos, ensure_ascii=False),
                        },
                    }
                    for ll in llamadas
                ],
            }
        case ResultadoLlamada(llamada_id=llamada_id, contenido=contenido):
            return {
                "role": "tool",
                "tool_call_id": llamada_id,
                # Compacto: los resultados de las tools son la parte variable más grande.
                "content": json.dumps(
                    contenido, ensure_ascii=False, default=str, separators=(",", ":")
                ),
            }
    raise TypeError(f"Mensaje desconocido: {type(mensaje).__name__}")


def _argumentos(crudos: str | None) -> dict[str, Any]:
    """El modelo manda los argumentos como texto JSON; si vienen mal, la tool los rechaza."""
    try:
        argumentos = json.loads(crudos or "{}")
    except json.JSONDecodeError:
        logger.info("Groq devolvió argumentos que no son JSON")
        return {}
    return argumentos if isinstance(argumentos, dict) else {}


def _error(exc: groq.APIStatusError) -> dict[str, Any]:
    cuerpo = exc.body if isinstance(exc.body, dict) else {}
    error = cuerpo.get("error", cuerpo)
    return error if isinstance(error, dict) else {}


def _codigo(exc: groq.APIStatusError) -> str:
    error = _error(exc)
    return str(error.get("code") or error.get("type") or "")


def _generacion_fallida(exc: groq.APIStatusError) -> str:
    return str(_error(exc).get("failed_generation") or "")
