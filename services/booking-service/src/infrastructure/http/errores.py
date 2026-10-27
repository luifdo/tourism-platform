"""Traducción de errores a HTTP con el formato común { error, message, correlation_id }."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from application import errores as app
from domain import errores as dom
from infrastructure.observabilidad.correlacion import correlation_id_actual

logger = logging.getLogger(__name__)

ESTADOS: dict[type[dom.ErrorDominio], int] = {
    dom.Validacion: 400,
    app.NoEncontrado: 404,
    app.RolNoPermitido: 403,
    dom.TransicionInvalida: 409,
    dom.PlazoVencido: 409,
    dom.FueraDePlazo: 409,
    dom.CuposInsuficientes: 409,
    dom.CuposComprometidos: 409,
    dom.NoDisponible: 409,
    app.ReservaDuplicada: 409,
    app.DiaExistente: 409,
    app.VersionDistinta: 409,
    dom.SuperaAforo: 422,
    app.FaltaIfMatch: 428,
    app.PeticionEnProceso: 409,
    app.IdempotenciaNoDisponible: 503,
}


class NoAutenticado(dom.ErrorDominio):
    """Sin X-Usuario-Id o X-Usuario-Rol: la petición no pasó por ForwardAuth."""

    codigo = "NO_AUTENTICADO"


ESTADOS[NoAutenticado] = 401


def correlation_id(request: Request) -> str:
    """El que fijó CorrelacionMiddleware; el encabezado queda como respaldo si no corrió."""
    return correlation_id_actual() or request.headers.get("X-Correlation-ID") or f"corr-{uuid4()}"


def respuesta_error(request: Request, estado: int, codigo: str, mensaje: str, **headers: str) -> JSONResponse:
    return JSONResponse(
        status_code=estado,
        content={"error": codigo, "message": mensaje, "correlation_id": correlation_id(request)},
        headers=headers or None,
    )


def registrar_manejadores(app_fastapi: FastAPI) -> None:
    @app_fastapi.exception_handler(dom.ErrorDominio)
    async def _dominio(request: Request, exc: dom.ErrorDominio) -> JSONResponse:
        estado = next((s for tipo, s in ESTADOS.items() if isinstance(exc, tipo)), 400)
        headers = {}
        if isinstance(exc, app.VersionDistinta):
            headers["ETag"] = f'"{exc.version_actual}"'
        return respuesta_error(request, estado, exc.codigo, exc.mensaje, **headers)

    @app_fastapi.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        detalles = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()
        )
        return respuesta_error(request, 400, "VALIDACION", detalles or "Datos inválidos.")

    @app_fastapi.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return respuesta_error(request, 500, "ERROR_INTERNO", "Ocurrió un error inesperado; reporte el correlation_id.")
