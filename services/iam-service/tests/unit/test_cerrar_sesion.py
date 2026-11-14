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
from tests.fakes import (
    FakeRedisClient,
    FakeRevocacion,
    FakeSesionesRenovacion,
    FakeUnitOfWork,
)

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
    return CerrarSesion(
        uow=uow, verificar=verificar, revocacion=rev, sesiones=FakeSesionesRenovacion()
    )


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


def caso_con_sesiones(
    llaves: LlavesRsa, uow: FakeUnitOfWork
) -> tuple[CerrarSesion, FakeRevocacion, FakeSesionesRenovacion]:
    rev = FakeRevocacion()
    sesiones = FakeSesionesRenovacion(rev)
    verificar = VerificarAcceso(tokens=crear_token_service(llaves), revocacion=rev)
    return (
        CerrarSesion(uow=uow, verificar=verificar, revocacion=rev, sesiones=sesiones),
        rev,
        sesiones,
    )


async def test_logout_revoca_la_familia_del_sid(llaves_rsa: LlavesRsa, uow: FakeUnitOfWork) -> None:
    caso, rev, sesiones = caso_con_sesiones(llaves_rsa, uow)
    assert USUARIO.id is not None
    await sesiones.crear(USUARIO.id, "familia-1", AHORA)
    emitido = crear_token_service(llaves_rsa).emitir(USUARIO, sid="familia-1")

    await caso.execute(emitido.access_token, None)

    assert sesiones.revocada("familia-1") is True
    assert emitido.jti in rev.revocados


async def test_token_sin_sid_no_revoca_ninguna_familia(
    llaves_rsa: LlavesRsa, uow: FakeUnitOfWork
) -> None:
    caso, rev, sesiones = caso_con_sesiones(llaves_rsa, uow)
    emitido = crear_token_service(llaves_rsa).emitir(USUARIO)

    await caso.execute(emitido.access_token, None)

    assert rev.sesiones_revocadas == set()
    assert sesiones.familias == {}
    assert emitido.jti in rev.revocados


async def test_si_falla_la_familia_el_token_sigue_sirviendo_para_reintentar(
    llaves_rsa: LlavesRsa, uow: FakeUnitOfWork
) -> None:
    # La familia va antes que el jti: al revés, el refresh quedaría vivo y el reintento daría 401.
    caso, rev, sesiones = caso_con_sesiones(llaves_rsa, uow)
    assert USUARIO.id is not None
    await sesiones.crear(USUARIO.id, "familia-1", AHORA)
    emitido = crear_token_service(llaves_rsa).emitir(USUARIO, sid="familia-1")
    sesiones.caida_al_revocar = True

    with pytest.raises(ServicioNoDisponibleError):
        await caso.execute(emitido.access_token, None)
    assert rev.revocados == {}

    sesiones.caida_al_revocar = False
    await caso.execute(emitido.access_token, None)
    assert sesiones.revocada("familia-1") is True


async def test_valkey_caido_falla_cerrado(llaves_rsa: LlavesRsa, uow: FakeUnitOfWork) -> None:
    access_token, _ = token(llaves_rsa)

    with pytest.raises(ServicioNoDisponibleError):
        await cerrar(llaves_rsa, uow, FakeRedisClient(caido=True)).execute(access_token, None)

    assert uow.auditoria.registros == []
