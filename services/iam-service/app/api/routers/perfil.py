"""UC4 y supresión de datos (Ley 1581): la cuenta del propio usuario, con cualquier rol."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import (
    get_cambiar_contrasena,
    get_editar_perfil,
    get_obtener_perfil,
    get_suprimir_datos,
    require_role,
)
from app.api.etag import etag, version_if_match
from app.api.ip_origen import ip_origen
from app.api.schemas.errors import ErrorResponse
from app.api.schemas.perfil import (
    CambiarContrasenaRequest,
    EditarPerfilRequest,
    PerfilResponse,
    SuprimirDatosRequest,
)
from app.application.use_cases.cambiar_contrasena import (
    CambiarContrasena,
    CambiarContrasenaCommand,
)
from app.application.use_cases.editar_perfil import EditarPerfil, EditarPerfilCommand
from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.application.use_cases.suprimir_datos import SuprimirDatos, SuprimirDatosCommand
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Idioma, Rol
from app.domain.value_objects.token import ClaimsToken

router = APIRouter(prefix="/api/iam/perfil", tags=["perfil"])

Autenticado = Annotated[ClaimsToken, Depends(require_role(*Rol))]

_ERROR_401 = {"model": ErrorResponse, "description": "TOKEN_INVALIDO"}
_ERROR_503 = {"model": ErrorResponse, "description": "SERVICIO_NO_DISPONIBLE"}


def _responder(response: Response, usuario: Usuario) -> PerfilResponse:
    response.headers["ETag"] = etag(usuario.version)
    # Datos personales: ninguna caché intermedia debe guardarlos.
    response.headers["Cache-Control"] = "no-store"
    return PerfilResponse.de(usuario)


@router.get("", response_model=PerfilResponse, responses={401: _ERROR_401})
async def mi_perfil(
    response: Response,
    claims: Autenticado,
    obtener: Annotated[ObtenerPerfil, Depends(get_obtener_perfil)],
) -> PerfilResponse:
    return _responder(response, await obtener.execute(uuid.UUID(claims.sub)))


@router.patch(
    "",
    response_model=PerfilResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _ERROR_401,
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "If-Match no coincide con la versión actual (VERSION_CONFLICTO).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "NOMBRE_INVALIDO, o idioma o campo no editable (VALIDACION).",
        },
    },
)
async def editar_perfil(
    request: Request,
    response: Response,
    body: EditarPerfilRequest,
    claims: Autenticado,
    editar: Annotated[EditarPerfil, Depends(get_editar_perfil)],
    version_esperada: Annotated[int | None, Depends(version_if_match)],
) -> PerfilResponse:
    usuario = await editar.execute(
        EditarPerfilCommand(
            usuario_id=uuid.UUID(claims.sub),
            nombre=body.nombre,
            idioma=Idioma(body.idioma) if body.idioma else None,
            version_esperada=version_esperada,
            ip_origen=ip_origen(request),
        )
    )
    return _responder(response, usuario)


@router.post(
    "/contrasena",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        status.HTTP_401_UNAUTHORIZED: _ERROR_401,
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "PASSWORD_ACTUAL_INCORRECTA o PASSWORD_INVALIDA.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: _ERROR_503,
    },
)
async def cambiar_contrasena(
    request: Request,
    body: CambiarContrasenaRequest,
    claims: Autenticado,
    cambiar: Annotated[CambiarContrasena, Depends(get_cambiar_contrasena)],
) -> Response:
    """Revoca todas las sesiones, también esta: la PWA debe iniciar sesión otra vez."""
    await cambiar.execute(
        CambiarContrasenaCommand(
            usuario_id=uuid.UUID(claims.sub),
            password_actual=body.password_actual,
            password_nueva=body.password_nueva,
            ip_origen=ip_origen(request),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "TOKEN_INVALIDO, o la contraseña no coincide (CREDENCIALES_INVALIDAS).",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Es el último Admin activo (ULTIMO_ADMIN).",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: _ERROR_503,
    },
)
async def suprimir_datos(
    request: Request,
    body: SuprimirDatosRequest,
    claims: Autenticado,
    suprimir: Annotated[SuprimirDatos, Depends(get_suprimir_datos)],
) -> Response:
    """Irreversible. Ante un 503 los tokens ya se revocaron: hay que iniciar sesión y repetirla."""
    await suprimir.execute(
        SuprimirDatosCommand(
            usuario_id=uuid.UUID(claims.sub),
            password=body.password,
            ip_origen=ip_origen(request),
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
