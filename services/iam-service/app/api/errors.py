from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas.errors import ErrorCampo, ErrorResponse
from app.domain.exceptions import (
    ArchivoDemasiadoGrandeError,
    AutogestionNoPermitidaError,
    CredencialesInvalidasError,
    CuentaInactivaError,
    DocumentoAprobadoError,
    DocumentoNoEncontradoError,
    DocumentosIncompletosError,
    DocumentoYaRevisadoError,
    DominioError,
    DominioValidationError,
    NoEsPrestadorError,
    RolInsuficienteError,
    ServicioNoDisponibleError,
    TokenInvalidoError,
    UltimoAdminError,
    UsuarioNoEncontradoError,
    UsuarioYaExisteError,
)
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual

Handler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _json(
    status_code: int, body: ErrorResponse, headers: dict[str, str] | None = None
) -> JSONResponse:
    body.correlation_id = correlation_id_actual()
    return JSONResponse(
        status_code=status_code, content=body.model_dump(exclude_none=True), headers=headers
    )


def _responder_con(status_code: int, headers: dict[str, str] | None = None) -> Handler:
    async def handler(_: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, DominioError):
            raise exc
        return _json(status_code, ErrorResponse(detail=exc.message, code=exc.code), headers)

    return handler


def _campo(loc: Sequence[Any]) -> str:
    # ("body", "email") -> "email"; si solo viene ("body",) el error es del cuerpo completo.
    return ".".join(str(parte) for parte in loc[1:]) or str(loc[0])


async def _validacion(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Solo "loc" y "msg": "input" repite el valor enviado (podría ser la contraseña),
    # y "ctx"/"url" no aportan al cliente.
    errores = [ErrorCampo(campo=_campo(e["loc"]), mensaje=e["msg"]) for e in exc.errors()]
    body = ErrorResponse(
        detail="Los datos enviados no son válidos.", code="VALIDACION", errores=errores
    )
    return _json(status.HTTP_422_UNPROCESSABLE_CONTENT, body)


def register_error_handlers(app: FastAPI) -> None:
    no_autenticado = _responder_con(
        status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"}
    )
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(CredencialesInvalidasError, no_autenticado)
    app.add_exception_handler(TokenInvalidoError, no_autenticado)
    app.add_exception_handler(CuentaInactivaError, _responder_con(status.HTTP_403_FORBIDDEN))
    app.add_exception_handler(RolInsuficienteError, _responder_con(status.HTTP_403_FORBIDDEN))
    app.add_exception_handler(
        ServicioNoDisponibleError, _responder_con(status.HTTP_503_SERVICE_UNAVAILABLE)
    )
    app.add_exception_handler(UsuarioYaExisteError, _responder_con(status.HTTP_409_CONFLICT))
    app.add_exception_handler(AutogestionNoPermitidaError, _responder_con(status.HTTP_409_CONFLICT))
    app.add_exception_handler(UltimoAdminError, _responder_con(status.HTTP_409_CONFLICT))
    conflicto = _responder_con(status.HTTP_409_CONFLICT)
    for error in (
        NoEsPrestadorError,
        DocumentoAprobadoError,
        DocumentosIncompletosError,
        DocumentoYaRevisadoError,
    ):
        app.add_exception_handler(error, conflicto)
    app.add_exception_handler(DocumentoNoEncontradoError, _responder_con(status.HTTP_404_NOT_FOUND))
    app.add_exception_handler(
        ArchivoDemasiadoGrandeError, _responder_con(status.HTTP_413_CONTENT_TOO_LARGE)
    )
    app.add_exception_handler(UsuarioNoEncontradoError, _responder_con(status.HTTP_404_NOT_FOUND))
    app.add_exception_handler(
        DominioValidationError, _responder_con(status.HTTP_422_UNPROCESSABLE_CONTENT)
    )
