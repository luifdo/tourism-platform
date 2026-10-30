from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import (
    auditar_token_rechazado,
    bearer,
    get_cerrar_sesion,
    get_iniciar_sesion,
    get_registrar_acceso_denegado,
    get_registrar_usuario,
    get_restablecer_contrasena,
    get_solicitar_recuperacion,
    get_tareas_segundo_plano,
    get_token_service,
    get_verificar_acceso,
)
from app.api.ip_origen import ip_origen
from app.api.schemas.auth import (
    JwksResponse,
    LoginRequest,
    LoginResponse,
    RecuperarRequest,
    RecuperarResponse,
    RegistroRequest,
    RestablecerRequest,
    UsuarioPublicoResponse,
)
from app.api.schemas.errors import ErrorResponse
from app.api.segundo_plano import TareasSegundoPlano
from app.application.use_cases.cerrar_sesion import CerrarSesion
from app.application.use_cases.iniciar_sesion import IniciarSesion, IniciarSesionCommand
from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.application.use_cases.registrar_usuario import RegistrarUsuario, RegistrarUsuarioCommand
from app.application.use_cases.restablecer_contrasena import (
    RestablecerContrasena,
    RestablecerContrasenaCommand,
)
from app.application.use_cases.solicitar_recuperacion import (
    SolicitarRecuperacion,
    SolicitarRecuperacionCommand,
)
from app.application.use_cases.verificar_acceso import VerificarAcceso
from app.domain.exceptions import TokenInvalidoError
from app.domain.value_objects.enums import Idioma, Rol
from app.infrastructure.observabilidad.metricas_recuperacion import SOLICITUDES_RECUPERACION
from app.infrastructure.security.jwt_token_service import JwtTokenService

router = APIRouter(prefix="/api/iam", tags=["auth"])

# Tope para la URI que se guarda en la bitácora (la envía el cliente a través de Traefik).
_MAX_URI = 2048


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UsuarioPublicoResponse,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "El correo ya está registrado (EMAIL_EN_USO).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": (
                "Petición inválida (VALIDACION, con la lista 'errores') o regla de negocio "
                "incumplida (HABEAS_DATA_REQUERIDO, MAYORIA_DE_EDAD_REQUERIDA, "
                "PASSWORD_INVALIDA, NOMBRE_INVALIDO)."
            ),
        },
    },
)
async def register(
    body: RegistroRequest,
    request: Request,
    registrar: Annotated[RegistrarUsuario, Depends(get_registrar_usuario)],
) -> UsuarioPublicoResponse:
    usuario = await registrar.execute(
        RegistrarUsuarioCommand(
            email=body.email,
            password=body.password,
            nombre_completo=body.nombre_completo,
            rol=Rol(body.rol),
            habeas_data_aceptado=body.habeas_data_aceptado,
            es_mayor_de_edad=body.es_mayor_de_edad,
            ip_origen=ip_origen(request),
            idioma=Idioma(body.idioma),
        )
    )
    return UsuarioPublicoResponse.model_validate(usuario)


_ERROR_401 = {
    "model": ErrorResponse,
    "description": "Correo o contraseña incorrectos (CREDENCIALES_INVALIDAS). "
    "Incluye el encabezado WWW-Authenticate: Bearer.",
}


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _ERROR_401,
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "La cuenta está desactivada (CUENTA_INACTIVA).",
        },
    },
)
async def login(
    body: LoginRequest,
    request: Request,
    iniciar: Annotated[IniciarSesion, Depends(get_iniciar_sesion)],
) -> LoginResponse:
    token, usuario = await iniciar.execute(
        IniciarSesionCommand(email=body.email, password=body.password, ip_origen=ip_origen(request))
    )
    return LoginResponse(
        access_token=token.access_token,
        expires_in=token.expires_in,
        usuario=UsuarioPublicoResponse.model_validate(usuario),
    )


_ERROR_TOKEN_401 = {
    "model": ErrorResponse,
    "description": "Token ausente, inválido, expirado o revocado (TOKEN_INVALIDO). "
    "Incluye el encabezado WWW-Authenticate: Bearer.",
}
_ERROR_503 = {
    "model": ErrorResponse,
    "description": "No se pudo consultar la lista de revocación (SERVICIO_NO_DISPONIBLE).",
}


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        status.HTTP_401_UNAUTHORIZED: _ERROR_TOKEN_401,
        status.HTTP_503_SERVICE_UNAVAILABLE: _ERROR_503,
    },
)
async def logout(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    cerrar: Annotated[CerrarSesion, Depends(get_cerrar_sesion)],
    registrar: Annotated[RegistrarAccesoDenegado, Depends(get_registrar_acceso_denegado)],
) -> Response:
    try:
        await cerrar.execute(credenciales.credentials if credenciales else None, ip_origen(request))
    except TokenInvalidoError as exc:
        # ESC-04: todo rechazo queda en la bitácora, también el del logout.
        await auditar_token_rechazado(registrar, exc, request, request.method, request.url.path)
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _sin_query(uri: str | None) -> str | None:
    # El query string puede traer datos personales o tokens: no va a la bitácora.
    if uri is None:
        return None
    return uri.split("?", 1)[0].split("#", 1)[0][:_MAX_URI]


@router.get(
    "/auth/verificar",
    response_class=Response,
    responses={
        status.HTTP_200_OK: {
            "description": "Token válido. Cuerpo vacío; la identidad va en los encabezados "
            "X-Usuario-Id y X-Usuario-Rol, que Traefik reenvía al servicio de destino.",
            "content": None,
        },
        status.HTTP_401_UNAUTHORIZED: _ERROR_TOKEN_401,
        status.HTTP_503_SERVICE_UNAVAILABLE: _ERROR_503,
    },
)
async def verificar(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verificar_acceso: Annotated[VerificarAcceso, Depends(get_verificar_acceso)],
    registrar: Annotated[RegistrarAccesoDenegado, Depends(get_registrar_acceso_denegado)],
    x_forwarded_method: Annotated[str | None, Header()] = None,
    x_forwarded_uri: Annotated[str | None, Header()] = None,
) -> Response:
    """RF-09: ForwardAuth de Traefik. Pública: la validación es este mismo endpoint.

    No consulta PostgreSQL en el camino feliz; solo escribe en la bitácora al rechazar.
    """
    try:
        claims = await verificar_acceso.execute(credenciales.credentials if credenciales else None)
    except TokenInvalidoError as exc:
        # Traefik envía el método y la URI de la petición original en X-Forwarded-*.
        await auditar_token_rechazado(
            registrar, exc, request, x_forwarded_method, _sin_query(x_forwarded_uri)
        )
        raise
    return Response(
        status_code=status.HTTP_200_OK,
        headers={
            "X-Usuario-Id": claims.sub,
            "X-Usuario-Rol": claims.rol.value,
            "Cache-Control": "no-store",
        },
    )


# Mismo cuerpo siempre: la respuesta no dice si el correo existe (C-28).
_RECUPERAR_RESPUESTA = RecuperarResponse(
    detail="Si el correo está registrado, recibirá un enlace para restablecer la contraseña."
)


async def _recuperar_y_medir(
    solicitar: SolicitarRecuperacion, cmd: SolicitarRecuperacionCommand
) -> None:
    resultado = await solicitar.execute(cmd)
    SOLICITUDES_RECUPERACION.labels(resultado=resultado).inc()


@router.post("/auth/recuperar", status_code=status.HTTP_202_ACCEPTED)
async def recuperar(
    body: RecuperarRequest,
    request: Request,
    solicitar: Annotated[SolicitarRecuperacion, Depends(get_solicitar_recuperacion)],
    tareas: Annotated[TareasSegundoPlano, Depends(get_tareas_segundo_plano)],
) -> RecuperarResponse:
    """UC3. Todo el trabajo corre después de responder: ni el tiempo ni un 503 revelan si el
    correo existe (C-50)."""
    cmd = SolicitarRecuperacionCommand(email=body.email, ip_origen=ip_origen(request))
    tareas.lanzar(_recuperar_y_medir(solicitar, cmd))
    return _RECUPERAR_RESPUESTA


@router.post(
    "/auth/restablecer",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Enlace inválido, vencido o ya usado (TOKEN_INVALIDO).",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "La contraseña no cumple la política (PASSWORD_INVALIDA); el enlace "
            "sigue sirviendo.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: _ERROR_503,
    },
)
async def restablecer(
    body: RestablecerRequest,
    request: Request,
    restablecer_contrasena: Annotated[RestablecerContrasena, Depends(get_restablecer_contrasena)],
) -> Response:
    await restablecer_contrasena.execute(
        RestablecerContrasenaCommand(
            token=body.token, password=body.password, ip_origen=ip_origen(request)
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/.well-known/jwks.json", response_model=JwksResponse)
async def jwks(
    response: Response, tokens: Annotated[JwtTokenService, Depends(get_token_service)]
) -> dict[str, Any]:
    """Llaves públicas para que el Gateway y los demás servicios verifiquen los tokens."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return tokens.jwks()
