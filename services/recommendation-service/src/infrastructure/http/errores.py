"""Errores con el formato común del contrato: `{error, message, correlation_id}`."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.application.instrucciones import Idioma
from src.application.ports.errores import DependenciaNoDisponibleError
from src.application.responder_mensaje import (
    AsistenteNoDisponibleError,
    ConversacionNoEncontradaError,
    DemasiadasSolicitudesError,
)

logger = logging.getLogger(__name__)

MENSAJES: dict[str, dict[Idioma, str]] = {
    "VALIDACION": {
        "es": "La petición no es válida: el mensaje debe tener entre 1 y 1000 caracteres.",
        "en": "Invalid request: the message must be between 1 and 1000 characters.",
    },
    "NO_AUTENTICADO": {
        "es": "Debes iniciar sesión para usar el asistente.",
        "en": "You must sign in to use the assistant.",
    },
    "PROHIBIDO": {
        "es": "El asistente está disponible solo para turistas.",
        "en": "The assistant is only available to tourists.",
    },
    "CONVERSACION_NO_ENCONTRADA": {
        "es": "La conversación no existe o expiró. Empieza una nueva.",
        "en": "The conversation does not exist or has expired. Start a new one.",
    },
    "DEMASIADAS_SOLICITUDES": {
        "es": "Enviaste muchos mensajes seguidos. Espera unos minutos e intenta de nuevo.",
        "en": "You sent too many messages in a row. Wait a few minutes and try again.",
    },
    "ASISTENTE_NO_DISPONIBLE": {
        "es": "El asistente no está disponible en este momento. Puedes seguir usando el catálogo.",
        "en": "The assistant is not available right now. You can keep using the catalog.",
    },
    "ERROR_INTERNO": {
        "es": "Ocurrió un error inesperado. Intenta de nuevo más tarde.",
        "en": "An unexpected error occurred. Please try again later.",
    },
}


class PeticionRechazadaError(Exception):
    def __init__(self, estado: int, codigo: str) -> None:
        super().__init__(codigo)
        self.estado = estado
        self.codigo = codigo


def idioma_de(accept_language: str | None) -> Idioma:
    return "en" if accept_language and accept_language.strip().lower().startswith("en") else "es"


def respuesta_de_error(request: Request, estado: int, codigo: str) -> JSONResponse:
    idioma = idioma_de(request.headers.get("Accept-Language"))
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid4())
    return JSONResponse(
        {"error": codigo, "message": MENSAJES[codigo][idioma], "correlation_id": correlation_id},
        status_code=estado,
        headers={"Content-Language": idioma},
    )


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, _: RequestValidationError) -> JSONResponse:
        # El contrato responde 400 VALIDACION, no el 422 de FastAPI.
        return respuesta_de_error(request, status.HTTP_400_BAD_REQUEST, "VALIDACION")

    @app.exception_handler(PeticionRechazadaError)
    async def _rechazada(request: Request, exc: PeticionRechazadaError) -> JSONResponse:
        return respuesta_de_error(request, exc.estado, exc.codigo)

    @app.exception_handler(ConversacionNoEncontradaError)
    async def _no_encontrada(request: Request, _: ConversacionNoEncontradaError) -> JSONResponse:
        return respuesta_de_error(request, status.HTTP_404_NOT_FOUND, "CONVERSACION_NO_ENCONTRADA")

    @app.exception_handler(DemasiadasSolicitudesError)
    async def _demasiadas(request: Request, _: DemasiadasSolicitudesError) -> JSONResponse:
        return respuesta_de_error(
            request, status.HTTP_429_TOO_MANY_REQUESTS, "DEMASIADAS_SOLICITUDES"
        )

    @app.exception_handler(AsistenteNoDisponibleError)
    @app.exception_handler(DependenciaNoDisponibleError)
    async def _no_disponible(request: Request, _: Exception) -> JSONResponse:
        # Proveedor de IA, PostgreSQL o Valkey caídos: para el turista es lo mismo.
        return respuesta_de_error(
            request, status.HTTP_503_SERVICE_UNAVAILABLE, "ASISTENTE_NO_DISPONIBLE"
        )

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        # Nunca una traza al cliente; el detalle queda en el log.
        logger.error("Error inesperado en %s", request.url.path, exc_info=exc)
        return respuesta_de_error(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "ERROR_INTERNO")
