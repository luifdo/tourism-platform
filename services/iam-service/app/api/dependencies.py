import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.ip_origen import ip_origen
from app.application.use_cases.cerrar_sesion import CerrarSesion
from app.application.use_cases.check_health import CheckHealth
from app.application.use_cases.iniciar_sesion import IniciarSesion
from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.application.use_cases.registrar_usuario import RegistrarUsuario
from app.application.use_cases.verificar_acceso import VerificarAcceso
from app.config import Settings, get_settings
from app.domain.exceptions import RolInsuficienteError, TokenInvalidoError
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.token_service import TokenService
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import Rol
from app.domain.value_objects.token import ClaimsToken
from app.infrastructure.cache.valkey_revocacion import ValkeyRevocacionTokens
from app.infrastructure.persistence.database import SqlAlchemyDatabaseProbe
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_token_service import LEEWAY_SEGUNDOS, JwtTokenService

# auto_error=False: sin token respondemos 401 TOKEN_INVALIDO con el formato de error común.
bearer = HTTPBearer(auto_error=False)


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def get_check_health(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckHealth:
    probe = SqlAlchemyDatabaseProbe(engine, settings.database_health_timeout_seconds)
    return CheckHealth(database=probe)


def get_unit_of_work(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


def get_reloj() -> Callable[[], datetime]:
    return lambda: datetime.now(UTC)


def get_token_service(request: Request) -> JwtTokenService:
    return request.app.state.token_service


def get_revocacion(
    request: Request,
    reloj: Annotated[Callable[[], datetime], Depends(get_reloj)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RevocacionTokens:
    # "revocado-desde" vive lo mismo que el token más largo que pudo emitirse antes del cambio.
    ttl = settings.jwt_access_token_ttl_minutes * 60 + LEEWAY_SEGUNDOS
    return ValkeyRevocacionTokens(request.app.state.valkey, reloj, ttl_revocado_desde=ttl)


def get_verificar_acceso(
    tokens: Annotated[TokenService, Depends(get_token_service)],
    revocacion: Annotated[RevocacionTokens, Depends(get_revocacion)],
) -> VerificarAcceso:
    return VerificarAcceso(tokens=tokens, revocacion=revocacion)


def get_registrar_acceso_denegado(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RegistrarAccesoDenegado:
    return RegistrarAccesoDenegado(uow=uow)


def get_iniciar_sesion(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> IniciarSesion:
    return IniciarSesion(uow=uow, hasher=hasher, tokens=tokens)


def get_cerrar_sesion(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    verificar: Annotated[VerificarAcceso, Depends(get_verificar_acceso)],
    revocacion: Annotated[RevocacionTokens, Depends(get_revocacion)],
) -> CerrarSesion:
    return CerrarSesion(uow=uow, verificar=verificar, revocacion=revocacion)


def get_registrar_usuario(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    reloj: Annotated[Callable[[], datetime], Depends(get_reloj)],
) -> RegistrarUsuario:
    return RegistrarUsuario(uow=uow, hasher=hasher, reloj=reloj)


async def auditar_token_rechazado(
    registrar: RegistrarAccesoDenegado,
    exc: TokenInvalidoError,
    request: Request,
    metodo: str | None,
    uri: str | None,
) -> None:
    """Fila ACCESS_DENIED de un 401. El motivo queda en la bitácora, no en la respuesta."""
    await registrar.execute(
        usuario_id=exc.usuario_id,
        ip_origen=ip_origen(request),
        detalles={"motivo": exc.motivo, "metodo": metodo, "uri": uri},
    )


def require_role(*roles: Rol) -> Callable[..., Awaitable[ClaimsToken]]:
    """Dependencia de RBAC: 401 si el token no sirve, 403 si el rol no está en `roles`.

    Devuelve los claims para que el endpoint sepa quién es el usuario.
    """
    requeridos = [rol.value for rol in roles]

    async def verificar_rol(
        request: Request,
        credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        verificar: Annotated[VerificarAcceso, Depends(get_verificar_acceso)],
        registrar: Annotated[RegistrarAccesoDenegado, Depends(get_registrar_acceso_denegado)],
    ) -> ClaimsToken:
        try:
            claims = await verificar.execute(credenciales.credentials if credenciales else None)
        except TokenInvalidoError as exc:
            await auditar_token_rechazado(registrar, exc, request, request.method, request.url.path)
            raise

        if claims.rol not in roles:
            ruta = request.scope.get("route")
            await registrar.execute(
                usuario_id=uuid.UUID(claims.sub),
                ip_origen=ip_origen(request),
                detalles={
                    "rol": claims.rol.value,
                    "requeridos": requeridos,
                    "metodo": request.method,
                    "ruta": request.url.path,
                    # Ruta declarada (con {parámetros}): permite agrupar por endpoint.
                    "plantilla": getattr(ruta, "path", None),
                },
            )
            raise RolInsuficienteError()
        return claims

    return verificar_rol
