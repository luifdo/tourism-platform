"""Traduce errores a respuestas HTTP con el formato común y en el idioma de la petición."""

import logging
from uuid import UUID

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.i18n.mensajes_error import mensaje_codigo, mensaje_error, mensaje_validacion
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.seguridad.ip_origen import ip_origen
from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.domain.errors import ErrorDominio, RolNoPermitido, VersionDistinta
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual

logger = logging.getLogger(__name__)

ESTADO_POR_CODIGO = {
    "VALIDACION": status.HTTP_400_BAD_REQUEST,
    "NO_ENCONTRADO": status.HTTP_404_NOT_FOUND,
    "ROL_NO_PERMITIDO": status.HTTP_403_FORBIDDEN,
    "PERFIL_INACTIVO": status.HTTP_403_FORBIDDEN,
    "VERSION_DISTINTA": status.HTTP_409_CONFLICT,
    "ZONA_EN_USO": status.HTTP_409_CONFLICT,
    "CODIGO_EXISTENTE": status.HTTP_409_CONFLICT,
    "ALERTA_RETIRADA": status.HTTP_409_CONFLICT,
    "FALTA_IF_MATCH": status.HTTP_428_PRECONDITION_REQUIRED,
    "NO_AUTENTICADO": status.HTTP_401_UNAUTHORIZED,
    "SOLICITUD_EN_PROCESO": status.HTTP_409_CONFLICT,
    "DEPENDENCIA_NO_DISPONIBLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "METODO_NO_PERMITIDO": status.HTTP_405_METHOD_NOT_ALLOWED,
}

# Tipos de error de Pydantic que corresponden a un dato faltante.
_FALTANTES = {"missing", "missing_argument"}


def _respuesta(
    estado: int, codigo: str, mensaje: str, idioma: Idioma, cabeceras: dict[str, str] | None = None
) -> JSONResponse:
    cuerpo = ErrorRespuesta(error=codigo, message=mensaje, correlation_id=correlation_id_actual())
    return JSONResponse(
        cuerpo.model_dump(),
        status_code=estado,
        headers={"Content-Language": idioma.value, **(cabeceras or {})},
    )


def _idioma(request: Request) -> Idioma:
    return Idioma.desde_accept_language(request.headers.get("accept-language"))


async def manejar_error_dominio(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorDominio)
    if isinstance(exc, RolNoPermitido):
        await _auditar_acceso_denegado(request, exc)
    idioma = _idioma(request)
    cabeceras = {"ETag": f'"{exc.version_actual}"'} if isinstance(exc, VersionDistinta) else None
    estado = ESTADO_POR_CODIGO.get(exc.codigo, status.HTTP_400_BAD_REQUEST)
    return _respuesta(estado, exc.codigo, mensaje_error(exc, idioma), idioma, cabeceras)


async def _auditar_acceso_denegado(request: Request, exc: RolNoPermitido) -> None:
    """ESC-04. Si no se puede guardar, se registra en el log y la respuesta 403 sale igual."""
    auditor: RegistrarAccesoDenegado | None = getattr(request.app.state, "auditor_accesos", None)
    if auditor is None:
        return
    try:
        await auditor.execute(
            usuario_id=_uuid_o_none(request.headers.get("x-usuario-id")),
            rol=exc.detalle.get("rol"),
            permitidos=list(exc.detalle.get("permitidos", [])),
            metodo=request.method,
            ruta=request.url.path,
            ip_origen=ip_origen(request),
        )
    except Exception:
        logger.exception("No se pudo auditar el acceso denegado a %s", request.url.path)


def _uuid_o_none(valor: str | None) -> UUID | None:
    try:
        return UUID(valor) if valor else None
    except ValueError:
        return None


async def manejar_validacion(request: Request, exc: Exception) -> JSONResponse:
    """Parámetros que no cumplen el esquema (tipos, rangos, faltantes) → VALIDACION 400."""
    assert isinstance(exc, RequestValidationError)
    idioma = _idioma(request)
    primero = exc.errors()[0] if exc.errors() else {}
    campo = str(primero.get("loc", ["?"])[-1])
    regla = "obligatorio" if primero.get("type") in _FALTANTES else "formato"
    return _respuesta(
        status.HTTP_400_BAD_REQUEST,
        "VALIDACION",
        mensaje_validacion(regla, idioma, {"campo": campo}),
        idioma,
    )


async def manejar_http(request: Request, exc: Exception) -> JSONResponse:
    """Errores que responde el propio FastAPI/Starlette (cuerpo que no es JSON, ruta que no
    existe, método no admitido), con el mismo formato `Error` e idioma que los demás."""
    assert isinstance(exc, HTTPException)
    idioma = _idioma(request)
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        codigo, mensaje = "NO_ENCONTRADO", mensaje_codigo("NO_ENCONTRADO", idioma)
    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        datos = {"metodo": request.method}
        codigo, mensaje = (
            "METODO_NO_PERMITIDO",
            mensaje_codigo("METODO_NO_PERMITIDO", idioma, datos),
        )
    else:  # 400: el cuerpo no se pudo leer como JSON
        codigo = "VALIDACION"
        mensaje = mensaje_validacion("formato", idioma, {"campo": "cuerpo"})
    return _respuesta(exc.status_code, codigo, mensaje, idioma, dict(exc.headers or {}))


async def manejar_inesperado(request: Request, exc: Exception) -> JSONResponse:
    # Este manejador corre fuera de los middlewares: la cabecera de correlación va aquí.
    logger.exception("Error inesperado atendiendo %s %s", request.method, request.url.path)
    idioma = _idioma(request)
    return _respuesta(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "ERROR_INTERNO",
        mensaje_codigo("ERROR_INTERNO", idioma),
        idioma,
        {"X-Correlation-ID": correlation_id_actual() or ""},
    )


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDominio, manejar_error_dominio)
    app.add_exception_handler(RequestValidationError, manejar_validacion)
    app.add_exception_handler(HTTPException, manejar_http)
    app.add_exception_handler(Exception, manejar_inesperado)
