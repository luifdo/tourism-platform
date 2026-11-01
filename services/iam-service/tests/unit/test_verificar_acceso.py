import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.application.use_cases.verificar_acceso import VerificarAcceso
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import ServicioNoDisponibleError, TokenInvalidoError
from app.domain.value_objects.enums import Rol
from tests.conftest import LlavesRsa, crear_token_service
from tests.fakes import FakeRevocacion

AHORA = datetime.now(UTC).replace(microsecond=0)
USUARIO = Usuario(
    id=uuid.uuid4(),
    email="maria.perez@example.com",
    password_hash="x",
    nombre_completo="María Pérez",
    rol=Rol.PRESTADOR,
    habeas_data_aceptado=True,
    habeas_data_aceptado_en=AHORA,
)


def caso(llaves: LlavesRsa, revocacion: FakeRevocacion) -> VerificarAcceso:
    return VerificarAcceso(tokens=crear_token_service(llaves), revocacion=revocacion)


async def test_token_valido_devuelve_los_claims(llaves_rsa: LlavesRsa) -> None:
    emitido = crear_token_service(llaves_rsa, reloj=AHORA).emitir(USUARIO)

    claims = await caso(llaves_rsa, FakeRevocacion()).execute(emitido.access_token)

    assert (claims.sub, claims.rol, claims.jti) == (str(USUARIO.id), Rol.PRESTADOR, emitido.jti)


async def test_sin_token(llaves_rsa: LlavesRsa) -> None:
    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(llaves_rsa, FakeRevocacion()).execute(None)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("sin_token", None)


async def test_token_invalido_no_identifica_al_usuario(llaves_rsa: LlavesRsa) -> None:
    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(llaves_rsa, FakeRevocacion()).execute("a.b.c")

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("invalido", None)


async def test_sub_que_no_es_uuid(llaves_rsa: LlavesRsa) -> None:
    # La hora de ahora y no AHORA, que se fija al importar: la suite puede tardar más de 5 minutos.
    ahora = datetime.now(UTC)
    claims = {
        "sub": "no-es-uuid",
        "rol": "Admin",
        "jti": "j",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=5),
        "iss": "iam-service",
        "typ": "access",
    }
    token = jwt.encode(claims, llaves_rsa.private_pem, algorithm="RS256")

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(llaves_rsa, FakeRevocacion()).execute(token)

    assert exc_info.value.motivo == "invalido"


async def test_revocado_por_jti(llaves_rsa: LlavesRsa) -> None:
    emitido = crear_token_service(llaves_rsa, reloj=AHORA).emitir(USUARIO)
    revocacion = FakeRevocacion()
    await revocacion.revocar(emitido.jti, emitido.expira_en)

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(llaves_rsa, revocacion).execute(emitido.access_token)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("revocado", USUARIO.id)


@pytest.mark.parametrize(
    ("desfase", "revocado"),
    [(0, True), (1, True), (-1, False)],
    ids=["mismo_segundo", "despues", "antes"],
)
async def test_revocado_desde(llaves_rsa: LlavesRsa, desfase: int, revocado: bool) -> None:
    # desfase: segundos entre la emisión del token y el cambio de rol/desactivación.
    emitido = crear_token_service(llaves_rsa, reloj=AHORA).emitir(USUARIO)
    revocacion = FakeRevocacion()
    assert USUARIO.id is not None
    await revocacion.revocar_usuario(USUARIO.id, desde=AHORA + timedelta(seconds=desfase))

    if revocado:
        with pytest.raises(TokenInvalidoError) as exc_info:
            await caso(llaves_rsa, revocacion).execute(emitido.access_token)
        assert exc_info.value.motivo == "revocado"
    else:
        await caso(llaves_rsa, revocacion).execute(emitido.access_token)


async def test_sesion_revocada_rechaza_solo_los_tokens_de_ese_sid(llaves_rsa: LlavesRsa) -> None:
    servicio = crear_token_service(llaves_rsa)
    de_la_sesion = servicio.emitir(USUARIO, sid="sesion-1")
    de_otra_sesion = servicio.emitir(USUARIO, sid="sesion-2")
    sin_sid = servicio.emitir(USUARIO)
    revocacion = FakeRevocacion()
    revocacion.sesiones_revocadas.add("sesion-1")

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(llaves_rsa, revocacion).execute(de_la_sesion.access_token)
    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("revocado", USUARIO.id)

    claims = await caso(llaves_rsa, revocacion).execute(de_otra_sesion.access_token)
    assert claims.sid == "sesion-2"
    assert (await caso(llaves_rsa, revocacion).execute(sin_sid.access_token)).sid is None


async def test_un_refresh_token_opaco_no_sirve_como_access_token(llaves_rsa: LlavesRsa) -> None:
    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(llaves_rsa, FakeRevocacion()).execute(secrets.token_urlsafe(32))

    assert exc_info.value.motivo == "invalido"


async def test_valkey_caido_falla_cerrado(llaves_rsa: LlavesRsa) -> None:
    emitido = crear_token_service(llaves_rsa, reloj=AHORA).emitir(USUARIO)

    with pytest.raises(ServicioNoDisponibleError):
        await caso(llaves_rsa, FakeRevocacion(caida=True)).execute(emitido.access_token)
