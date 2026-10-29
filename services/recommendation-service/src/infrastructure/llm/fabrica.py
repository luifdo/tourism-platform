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
    """Elige el adaptador según LLM_PROVIDER. El de Groq se agrega en la Fase 5."""
    if config.llm_provider:
        logger.warning(
            "LLM_PROVIDER=%s todavía no tiene adaptador; el chat responderá 503",
            config.llm_provider,
        )
    return SinProveedor()
