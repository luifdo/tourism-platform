import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.ip_origen import ip_origen
from app.api.segundo_plano import TareasSegundoPlano
from app.application.use_cases.abrir_documento import AbrirDocumento
from app.application.use_cases.aprobar_prestador import AprobarPrestador
from app.application.use_cases.cambiar_contrasena import CambiarContrasena
from app.application.use_cases.cambiar_estado_usuario import CambiarEstadoUsuario
from app.application.use_cases.cambiar_rol_usuario import CambiarRolUsuario
from app.application.use_cases.cerrar_sesion import CerrarSesion
from app.application.use_cases.check_health import CheckHealth
from app.application.use_cases.consultar_bitacora import ConsultarBitacora
from app.application.use_cases.consultar_verificacion import ConsultarVerificacion
from app.application.use_cases.editar_perfil import EditarPerfil
from app.application.use_cases.iniciar_sesion import IniciarSesion
from app.application.use_cases.listar_prestadores import ListarPrestadores
from app.application.use_cases.listar_usuarios import ListarUsuarios
from app.application.use_cases.obtener_contacto_usuario import ObtenerContactoUsuario
from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.application.use_cases.obtener_usuario import ObtenerUsuario
from app.application.use_cases.rechazar_prestador import RechazarPrestador
from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.application.use_cases.registrar_usuario import RegistrarUsuario
from app.application.use_cases.restablecer_contrasena import RestablecerContrasena
from app.application.use_cases.solicitar_recuperacion import SolicitarRecuperacion
from app.application.use_cases.subir_documento import SubirDocumento
from app.application.use_cases.suprimir_datos import SuprimirDatos
from app.application.use_cases.verificar_acceso import VerificarAcceso
from app.config import Settings, get_settings
from app.domain.exceptions import RolInsuficienteError, TokenInvalidoError
from app.domain.ports.almacen_documentos import AlmacenDocumentos
from app.domain.ports.enviador_correo import EnviadorCorreo
from app.domain.ports.password_hasher import PasswordHasher
from app.domain.ports.revocacion_tokens import RevocacionTokens
from app.domain.ports.token_service import TokenService
from app.domain.ports.tokens_recuperacion import TokensRecuperacion
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import Rol
from app.domain.value_objects.token import ClaimsToken
from app.infrastructure.cache.valkey_probe import ValkeyProbe
from app.infrastructure.cache.valkey_revocacion import ValkeyRevocacionTokens
from app.infrastructure.cache.valkey_tokens_recuperacion import ValkeyTokensRecuperacion
from app.infrastructure.persistence.database import SqlAlchemyDatabaseProbe
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.jwt_token_service import LEEWAY_SEGUNDOS, JwtTokenService

# auto_error=False: sin token respondemos 401 TOKEN_INVALIDO con el formato de error común.
bearer = HTTPBearer(auto_error=False)


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def get_check_health(
    request: Request,
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckHealth:
    return CheckHealth(
        database=SqlAlchemyDatabaseProbe(engine, settings.database_health_timeout_seconds),
        cache=ValkeyProbe(request.app.state.valkey, settings.valkey_health_timeout_seconds),
    )


def get_unit_of_work(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)


def get_password_hasher(request: Request) -> PasswordHasher:
    return request.app.state.password_hasher


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


def get_obtener_contacto_usuario(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ObtenerContactoUsuario:
    return ObtenerContactoUsuario(uow=uow)


def get_almacen_documentos(request: Request) -> AlmacenDocumentos:
    return request.app.state.almacen_documentos


def get_tokens_recuperacion(request: Request) -> TokensRecuperacion:
    return ValkeyTokensRecuperacion(request.app.state.valkey)


def get_enviador_correo(request: Request) -> EnviadorCorreo:
    return request.app.state.enviador_correo


def get_tareas_segundo_plano(request: Request) -> TareasSegundoPlano:
    return request.app.state.tareas_segundo_plano


Reloj = Annotated[Callable[[], datetime], Depends(get_reloj)]
Uow = Annotated[UnitOfWork, Depends(get_unit_of_work)]
Almacen = Annotated[AlmacenDocumentos, Depends(get_almacen_documentos)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
Revocacion = Annotated[RevocacionTokens, Depends(get_revocacion)]
Tokens = Annotated[TokensRecuperacion, Depends(get_tokens_recuperacion)]
Enviador = Annotated[EnviadorCorreo, Depends(get_enviador_correo)]
Ajustes = Annotated[Settings, Depends(get_settings)]


def get_obtener_perfil(uow: Uow) -> ObtenerPerfil:
    return ObtenerPerfil(uow=uow)


def get_editar_perfil(uow: Uow) -> EditarPerfil:
    return EditarPerfil(uow=uow)


def get_cambiar_contrasena(
    uow: Uow, hasher: Hasher, revocacion: Revocacion, reloj: Reloj
) -> CambiarContrasena:
    return CambiarContrasena(uow=uow, hasher=hasher, revocacion=revocacion, reloj=reloj)


def get_solicitar_recuperacion(
    uow: Uow, tokens: Tokens, enviador: Enviador, settings: Ajustes
) -> SolicitarRecuperacion:
    return SolicitarRecuperacion(
        uow=uow, tokens=tokens, enviador=enviador, pwa_url=settings.pwa_url
    )


def get_restablecer_contrasena(
    uow: Uow, tokens: Tokens, hasher: Hasher, revocacion: Revocacion, reloj: Reloj
) -> RestablecerContrasena:
    return RestablecerContrasena(
        uow=uow, tokens=tokens, hasher=hasher, revocacion=revocacion, reloj=reloj
    )


def get_suprimir_datos(
    uow: Uow, hasher: Hasher, almacen: Almacen, revocacion: Revocacion, reloj: Reloj
) -> SuprimirDatos:
    return SuprimirDatos(
        uow=uow, hasher=hasher, almacen=almacen, revocacion=revocacion, reloj=reloj
    )


def get_subir_documento(uow: Uow, almacen: Almacen, reloj: Reloj) -> SubirDocumento:
    return SubirDocumento(uow=uow, almacen=almacen, reloj=reloj)


def get_consultar_verificacion(uow: Uow) -> ConsultarVerificacion:
    return ConsultarVerificacion(uow=uow)


def get_listar_prestadores(uow: Uow) -> ListarPrestadores:
    return ListarPrestadores(uow=uow)


def get_abrir_documento(uow: Uow, almacen: Almacen, reloj: Reloj) -> AbrirDocumento:
    return AbrirDocumento(uow=uow, almacen=almacen, reloj=reloj)


def get_aprobar_prestador(uow: Uow, reloj: Reloj) -> AprobarPrestador:
    return AprobarPrestador(uow=uow, reloj=reloj)


def get_rechazar_prestador(uow: Uow, reloj: Reloj) -> RechazarPrestador:
    return RechazarPrestador(uow=uow, reloj=reloj)


def get_consultar_bitacora(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ConsultarBitacora:
    return ConsultarBitacora(uow=uow)


def get_listar_usuarios(uow: Annotated[UnitOfWork, Depends(get_unit_of_work)]) -> ListarUsuarios:
    return ListarUsuarios(uow=uow)


def get_obtener_usuario(uow: Annotated[UnitOfWork, Depends(get_unit_of_work)]) -> ObtenerUsuario:
    return ObtenerUsuario(uow=uow)


def get_cambiar_rol_usuario(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    revocacion: Annotated[RevocacionTokens, Depends(get_revocacion)],
    reloj: Annotated[Callable[[], datetime], Depends(get_reloj)],
) -> CambiarRolUsuario:
    return CambiarRolUsuario(uow=uow, revocacion=revocacion, reloj=reloj)


def get_cambiar_estado_usuario(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    revocacion: Annotated[RevocacionTokens, Depends(get_revocacion)],
    reloj: Annotated[Callable[[], datetime], Depends(get_reloj)],
) -> CambiarEstadoUsuario:
    return CambiarEstadoUsuario(uow=uow, revocacion=revocacion, reloj=reloj)


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
