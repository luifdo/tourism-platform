import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.cerrar_sesion import CerrarSesion
from app.application.use_cases.verificar_acceso import VerificarAcceso
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import ServicioNoDisponibleError, TokenInvalidoError
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.infrastructure.cache.valkey_revocacion import ValkeyRevocacionTokens
from tests.conftest import LlavesRsa, crear_token_service
from tests.fakes import FakeRedisClient, FakeUnitOfWork

AHORA = datetime.now(UTC).replace(microsecond=0)
USUARIO = Usuario(
    id=uuid.uuid4(),
    email="maria.perez@example.com",
    password_hash="x",
    nombre_completo="María Pérez",
    rol=Rol.TURISTA,
    habeas_data_aceptado=True,
    habeas_data_aceptado_en=AHORA,
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


def revocacion(redis: FakeRedisClient, segundos_despues: int = 60) -> ValkeyRevocacionTokens:
    return ValkeyRevocacionTokens(
        redis,  # type: ignore[arg-type]
        reloj=lambda: AHORA + timedelta(seconds=segundos_despues),
        ttl_revocado_desde=910,
    )


def cerrar(
    llaves: LlavesRsa, uow: FakeUnitOfWork, redis: FakeRedisClient, segundos_despues: int = 60
) -> CerrarSesion:
    # La revocación ocurre `segundos_despues` de emitido el token.
    rev = revocacion(redis, segundos_despues)
    verificar = VerificarAcceso(tokens=crear_token_service(llaves), revocacion=rev)
    return CerrarSesion(uow=uow, verificar=verificar, revocacion=rev)


def token(llaves: LlavesRsa) -> tuple[str, str]:
    emitido = crear_token_service(llaves, reloj=AHORA).emitir(USUARIO)
    return emitido.access_token, emitido.jti


async def test_revoca_con_el_ttl_restante(llaves_rsa: LlavesRsa, uow: FakeUnitOfWork) -> None:
    redis = FakeRedisClient()
    access_token, jti = token(llaves_rsa)

    await cerrar(llaves_rsa, uow, redis, segundos_despues=60).execute(access_token, "190.0.0.1")

    # 15 min de vida - 60 s transcurridos = 840 s.
    assert redis.ttls == {f"iam:revoked:{jti}": 840}
    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("LOGOUT", ResultadoAuditoria.EXITO)
    assert registro.usuario_id == USUARIO.id
    assert registro.ip_origen == "190.0.0.1"


async def test_ttl_minimo_de_un_segundo() -> None:
    redis = FakeRedisClient()

    await revocacion(redis, segundos_despues=0).revocar(
        "jti-ya-vencido", expira_en=AHORA - timedelta(seconds=30)
    )

    assert redis.ttls == {"iam:revoked:jti-ya-vencido": 1}


async def test_token_ya_revocado(llaves_rsa: LlavesRsa, uow: FakeUnitOfWork) -> None:
    redis = FakeRedisClient()
    access_token, _ = token(llaves_rsa)
    caso = cerrar(llaves_rsa, uow, redis)
    await caso.execute(access_token, None)

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso.execute(access_token, None)

    assert exc_info.value.motivo == "revocado"
    assert [r.accion for r in uow.auditoria.registros] == ["LOGOUT"]


async def test_token_revocado_por_usuario(llaves_rsa: LlavesRsa, uow: FakeUnitOfWork) -> None:
    redis = FakeRedisClient()
    access_token, _ = token(llaves_rsa)
    assert USUARIO.id is not None
    await revocacion(redis).revocar_usuario(USUARIO.id, desde=AHORA)

    with pytest.raises(TokenInvalidoError) as exc_info:
        await cerrar(llaves_rsa, uow, redis).execute(access_token, None)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("revocado", USUARIO.id)
    assert uow.auditoria.registros == []


@pytest.mark.parametrize(("valor", "motivo"), [(None, "sin_token"), ("no-es-un-token", "invalido")])
async def test_token_invalido(
    llaves_rsa: LlavesRsa, uow: FakeUnitOfWork, valor: str | None, motivo: str
) -> None:
    redis = FakeRedisClient()

    with pytest.raises(TokenInvalidoError) as exc_info:
        await cerrar(llaves_rsa, uow, redis).execute(valor, None)

    assert exc_info.value.motivo == motivo
    assert redis.ttls == {}
    assert uow.auditoria.registros == []


async def test_valkey_caido_falla_cerrado(llaves_rsa: LlavesRsa, uow: FakeUnitOfWork) -> None:
    access_token, _ = token(llaves_rsa)

    with pytest.raises(ServicioNoDisponibleError):
        await cerrar(llaves_rsa, uow, FakeRedisClient(caido=True)).execute(access_token, None)

    assert uow.auditoria.registros == []
