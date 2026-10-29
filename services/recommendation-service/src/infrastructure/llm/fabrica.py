import logging
from collections.abc import Sequence

from src.application.ports.herramientas import DeclaracionHerramienta
from src.application.ports.modelo_de_lenguaje import (
    MensajeModelo,
    ModeloDeLenguaje,
    ModeloNoDisponibleError,
    RespuestaModelo,
)
from src.config import Configuracion
from src.infrastructure.llm.modelo_groq import crear_modelo_groq

logger = logging.getLogger(__name__)


class SinProveedor:
    """Lo que se usa mientras no haya un proveedor conectado: el chat responde 503.

    No es un proveedor falso: no inventa respuestas. El resto del servicio funciona igual.
    """

    nombre = "sin-proveedor"

    async def generar(
        self,
        instrucciones: str,
        mensajes: Sequence[MensajeModelo],
        herramientas: Sequence[DeclaracionHerramienta],
    ) -> RespuestaModelo:
        raise ModeloNoDisponibleError("No hay un proveedor de IA configurado (LLM_PROVIDER).")


def crear_modelo(config: Configuracion) -> ModeloDeLenguaje:
    """Elige el adaptador según LLM_PROVIDER. Agregar un proveedor es agregar una rama aquí."""
    proveedor = config.llm_provider.strip().lower()
    clave = config.llm_api_key.get_secret_value().strip()
    if proveedor == "groq":
        if not clave:
            logger.warning("LLM_PROVIDER=groq sin LLM_API_KEY; el chat responderá 503")
            return SinProveedor()
        return crear_modelo_groq(
            clave,
            config.llm_model,
            config.llm_reasoning_effort,
            # El modelo nunca puede tardar más que la consulta completa.
            timeout_segundos=config.chat_timeout_segundos,
        )
    if proveedor:
        logger.warning("LLM_PROVIDER=%s no tiene adaptador; el chat responderá 503", proveedor)
    return SinProveedor()
