from collections.abc import Callable
from dataclasses import replace

import pytest

from app.application.use_cases.iniciar_sesion import (
    HASH_RELLENO,
    IniciarSesion,
    IniciarSesionCommand,
)
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    CredencialesInvalidasError,
    CuentaInactivaError,
    ServicioNoDisponibleError,
)
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.infrastructure.security.jwt_token_service import JwtTokenService
from tests.fakes import AHORA, FakePasswordHasher, FakeSesionesRenovacion, FakeUnitOfWork

PASSWORD = "Tayrona2026"
COMANDO = IniciarSesionCommand(
    email="  Maria.Perez@Example.com ", password=PASSWORD, ip_origen="190.0.0.1"
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


def sembrar(uow: FakeUnitOfWork, hasher: FakePasswordHasher, activo: bool = True) -> Usuario:
    return uow.usuarios.sembrar(
        Usuario(
            email="maria.perez@example.com",
            password_hash=hasher.hash(PASSWORD),
            nombre_completo="María Pérez",
            rol=Rol.TURISTA,
            activo=activo,
            email_verificado=False,
            habeas_data_aceptado=True,
            habeas_data_aceptado_en=AHORA,
        )
    )


def iniciar(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    token_service: JwtTokenService,
    sesiones: FakeSesionesRenovacion | None = None,
) -> IniciarSesion:
    return IniciarSesion(
        uow=uow,
        hasher=hasher,
        tokens=token_service,
        sesiones=sesiones or FakeSesionesRenovacion(),
    )


class HasherQueCambiaLaCuenta(FakePasswordHasher):
    """Simula un cambio confirmado mientras el login esperaba su turno de Argon2 (C-53)."""

    def __init__(self) -> None:
        super().__init__()
        self.durante_el_hash: Callable[[], None] = lambda: None

    async def verify_limitado(self, plain: str, hashed: str) -> bool:
        self.durante_el_hash()
        return await super().verify_limitado(plain, hashed)


async def test_login_emite_el_rol_vigente_si_cambio_durante_el_hash(
    uow: FakeUnitOfWork, token_service: JwtTokenService
) -> None:
    hasher = HasherQueCambiaLaCuenta()
    existente = sembrar(uow, hasher)

    def degradar() -> None:
        uow.usuarios.por_email[existente.email] = replace(existente, rol=Rol.ENTIDAD)

    hasher.durante_el_hash = degradar
    token, usuario, _ = await iniciar(uow, hasher, token_service).execute(COMANDO)

    assert usuario.rol is Rol.ENTIDAD
    assert token_service.verificar(token.access_token).rol is Rol.ENTIDAD


async def test_login_rechaza_si_la_cuenta_se_desactivo_durante_el_hash(
    uow: FakeUnitOfWork, token_service: JwtTokenService
) -> None:
    hasher = HasherQueCambiaLaCuenta()
    existente = sembrar(uow, hasher)

    def desactivar() -> None:
        uow.usuarios.por_email[existente.email] = replace(existente, activo=False)

    hasher.durante_el_hash = desactivar
    with pytest.raises(CuentaInactivaError):
        await iniciar(uow, hasher, token_service).execute(COMANDO)

    [registro] = uow.auditoria.registros
    assert registro.detalles == {"motivo": "cuenta_inactiva"}


async def test_login_rechaza_si_la_contrasena_cambio_durante_el_hash(
    uow: FakeUnitOfWork, token_service: JwtTokenService
) -> None:
    hasher = HasherQueCambiaLaCuenta()
    existente = sembrar(uow, hasher)

    def cambiar() -> None:
        uow.usuarios.por_email[existente.email] = replace(existente, password_hash="otro")

    hasher.durante_el_hash = cambiar
    with pytest.raises(CredencialesInvalidasError):
        await iniciar(uow, hasher, token_service).execute(COMANDO)

    [registro] = uow.auditoria.registros
    assert registro.resultado is ResultadoAuditoria.DENEGADO
    assert registro.detalles == {"motivo": "password_incorrecta"}


async def test_login_exitoso(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService
) -> None:
    existente = sembrar(uow, hasher)

    token, usuario, _ = await iniciar(uow, hasher, token_service).execute(COMANDO)

    assert usuario.id == existente.id
    assert usuario.email_verificado is False  # no bloquea el login por ahora
    claims = token_service.verificar(token.access_token)
    assert claims.sub == str(existente.id)
    assert claims.rol is Rol.TURISTA
    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("LOGIN_SUCCESS", ResultadoAuditoria.EXITO)
    assert registro.usuario_id == existente.id
    assert registro.ip_origen == "190.0.0.1"
    # Sin rehash: el hash guardado no cambia.
    assert uow.usuarios.por_email[existente.email].password_hash == existente.password_hash


async def test_login_crea_la_familia_con_el_sid_y_el_iat_del_token(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService
) -> None:
    sembrar(uow, hasher)
    sesiones = FakeSesionesRenovacion()

    token, _, sesion = await iniciar(uow, hasher, token_service, sesiones).execute(COMANDO)

    claims = token_service.verificar(token.access_token)
    assert claims.sid == sesion.familia
    # Con el iat, el access token y el refresh quedan del mismo lado de una marca (C-21).
    assert sesiones.familias[sesion.familia]["renovado_en"] == int(claims.iat.timestamp())
    assert sesiones.familias[sesion.familia]["actual"] == sesion.refresh_token


async def test_login_con_valkey_caido_no_confirma_nada(
    uow: FakeUnitOfWork, token_service: JwtTokenService
) -> None:
    # Con un rehash por aplicar: tampoco se confirma el hash nuevo.
    sembrar(uow, FakePasswordHasher(version=1))
    hasher_actual = FakePasswordHasher(version=2)

    with pytest.raises(ServicioNoDisponibleError):
        await iniciar(
            uow, hasher_actual, token_service, FakeSesionesRenovacion(caida=True)
        ).execute(COMANDO)

    assert uow.commits == 0
    assert uow.rollbacks == 2  # la lectura inicial y la transacción del login
    assert uow.auditoria.registros == []


async def test_password_incorrecta(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService
) -> None:
    existente = sembrar(uow, hasher)

    with pytest.raises(CredencialesInvalidasError):
        await iniciar(uow, hasher, token_service).execute(replace(COMANDO, password="otra123"))

    assert uow.commits == 1  # el fallo queda confirmado en la bitácora
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("LOGIN_FAIL", ResultadoAuditoria.DENEGADO)
    assert registro.usuario_id == existente.id
    assert registro.detalles == {"motivo": "password_incorrecta"}


@pytest.mark.parametrize("email", ["nadie@example.com", "no-es-un-email"])
async def test_usuario_inexistente_verifica_contra_el_hash_de_relleno(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService, email: str
) -> None:
    sembrar(uow, hasher)

    with pytest.raises(CredencialesInvalidasError):
        await iniciar(uow, hasher, token_service).execute(replace(COMANDO, email=email))

    assert hasher.verificados == [HASH_RELLENO]
    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("LOGIN_FAIL", ResultadoAuditoria.DENEGADO)
    assert registro.usuario_id is None
    assert registro.detalles == {"motivo": "usuario_no_existe"}  # sin el correo intentado


async def test_cuenta_inactiva(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService
) -> None:
    existente = sembrar(uow, hasher, activo=False)

    with pytest.raises(CuentaInactivaError):
        await iniciar(uow, hasher, token_service).execute(COMANDO)

    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("LOGIN_FAIL", ResultadoAuditoria.DENEGADO)
    assert registro.usuario_id == existente.id
    assert registro.detalles == {"motivo": "cuenta_inactiva"}


async def test_cuenta_inactiva_con_password_incorrecta_no_revela_el_estado(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService
) -> None:
    sembrar(uow, hasher, activo=False)

    with pytest.raises(CredencialesInvalidasError):
        await iniciar(uow, hasher, token_service).execute(replace(COMANDO, password="otra123"))

    assert uow.auditoria.registros[0].detalles == {"motivo": "password_incorrecta"}


async def test_rehash_cuando_los_parametros_cambiaron(
    uow: FakeUnitOfWork, token_service: JwtTokenService
) -> None:
    existente = sembrar(uow, FakePasswordHasher(version=1))
    hasher_actual = FakePasswordHasher(version=2)

    await iniciar(uow, hasher_actual, token_service).execute(COMANDO)

    guardado = uow.usuarios.por_email[existente.email].password_hash
    assert guardado != existente.password_hash
    assert guardado == hasher_actual.hash(PASSWORD)
    assert uow.commits == 1  # rehash y LOGIN_SUCCESS en la misma transacción
    assert [r.accion for r in uow.auditoria.registros] == ["LOGIN_SUCCESS"]


async def test_sin_rehash_si_los_parametros_no_cambiaron(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, token_service: JwtTokenService
) -> None:
    existente = sembrar(uow, hasher)

    await iniciar(uow, hasher, token_service).execute(COMANDO)

    assert uow.usuarios.por_email[existente.email].password_hash == existente.password_hash
