import base64
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import TokenInvalidoError
from app.domain.value_objects.enums import Rol
from app.infrastructure.security.jwt_token_service import JwtTokenService, LlavesJwtError
from tests.conftest import LlavesRsa, crear_token_service, generar_llaves_rsa


def usuario(rol: Rol = Rol.PRESTADOR) -> Usuario:
    return Usuario(
        id=uuid.uuid4(),
        email="maria.perez@example.com",
        password_hash="x",
        nombre_completo="María Pérez",
        rol=rol,
        habeas_data_aceptado=True,
        habeas_data_aceptado_en=datetime.now(UTC),
    )


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def segmento(obj: dict[str, Any]) -> str:
    return b64url(json.dumps(obj, separators=(",", ":")).encode())


def test_emitir_y_verificar_devuelve_los_mismos_claims(token_service: JwtTokenService) -> None:
    u = usuario()

    emitido = token_service.emitir(u)
    claims = token_service.verificar(emitido.access_token)

    assert claims.sub == str(u.id)
    assert claims.rol is Rol.PRESTADOR
    assert claims.jti == emitido.jti
    assert claims.exp == emitido.expira_en
    assert claims.exp - claims.iat == timedelta(minutes=15)
    assert emitido.expires_in == 900

    payload = jwt.decode(emitido.access_token, options={"verify_signature": False})
    assert payload["iss"] == "iam-service"
    assert payload["typ"] == "access"
    assert set(payload) == {"sub", "rol", "jti", "iat", "exp", "iss", "typ"}


def test_encabezado_trae_kid_y_rs256(token_service: JwtTokenService) -> None:
    header = jwt.get_unverified_header(token_service.emitir(usuario()).access_token)

    assert header["alg"] == "RS256"
    assert header["kid"] == token_service.kid


def test_token_emitido_no_muestra_el_token_en_repr(token_service: JwtTokenService) -> None:
    emitido = token_service.emitir(usuario())

    assert emitido.access_token not in repr(emitido)


def test_token_expirado(llaves_rsa: LlavesRsa) -> None:
    hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    u = usuario()
    viejo = crear_token_service(llaves_rsa, reloj=hace_una_hora).emitir(u)

    with pytest.raises(TokenInvalidoError) as exc_info:
        crear_token_service(llaves_rsa).verificar(viejo.access_token)

    # La firma es válida aunque haya expirado: se conoce al usuario para la bitácora.
    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("expirado", u.id)
    assert exc_info.value.message == "El token no es válido, expiró o fue revocado."


def test_token_expirado_con_sub_que_no_es_uuid(
    llaves_rsa: LlavesRsa, token_service: JwtTokenService
) -> None:
    hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    claims = {
        **_claims_validos(token_service),
        "sub": "no-es-uuid",
        "iat": hace_una_hora,
        "exp": hace_una_hora + timedelta(minutes=15),
    }
    token = jwt.encode(claims, llaves_rsa.private_pem, algorithm="RS256")

    with pytest.raises(TokenInvalidoError) as exc_info:
        token_service.verificar(token)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("expirado", None)


def test_expiracion_dentro_del_margen_de_10_segundos(llaves_rsa: LlavesRsa) -> None:
    # Expiró hace 5 s: el leeway de 10 s lo acepta todavía.
    reloj = datetime.now(UTC) - timedelta(minutes=15, seconds=5)
    token = crear_token_service(llaves_rsa, reloj=reloj).emitir(usuario())

    crear_token_service(llaves_rsa).verificar(token.access_token)


def test_firma_alterada(token_service: JwtTokenService) -> None:
    header, payload, firma = token_service.emitir(usuario(Rol.TURISTA)).access_token.split(".")
    # Mismo token pero con el rol cambiado a Admin: la firma ya no corresponde.
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["rol"] = "Admin"
    alterado = f"{header}.{segmento(claims)}.{firma}"

    with pytest.raises(TokenInvalidoError):
        token_service.verificar(alterado)


def test_firma_con_otra_llave(token_service: JwtTokenService) -> None:
    otra_privada, otra_publica = generar_llaves_rsa()
    ajeno = JwtTokenService(
        otra_privada,
        otra_publica,
        issuer="iam-service",
        ttl=timedelta(minutes=15),
        reloj=lambda: datetime.now(UTC),
    ).emitir(usuario())

    with pytest.raises(TokenInvalidoError) as exc_info:
        token_service.verificar(ajeno.access_token)

    # Firma no válida: no se puede confiar en el sub.
    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("invalido", None)


def test_typ_distinto_de_access(llaves_rsa: LlavesRsa, token_service: JwtTokenService) -> None:
    claims = {**_claims_validos(token_service), "typ": "refresh"}
    token = jwt.encode(claims, llaves_rsa.private_pem, algorithm="RS256")

    with pytest.raises(TokenInvalidoError) as exc_info:
        token_service.verificar(token)

    # La firma es válida: se conoce al usuario para la bitácora.
    assert exc_info.value.motivo == "tipo"
    assert exc_info.value.usuario_id == uuid.UUID(claims["sub"])


def test_otro_emisor(llaves_rsa: LlavesRsa, token_service: JwtTokenService) -> None:
    ajeno = crear_token_service(llaves_rsa, issuer="otro-servicio").emitir(usuario())

    with pytest.raises(TokenInvalidoError):
        token_service.verificar(ajeno.access_token)


def _claims_validos(token_service: JwtTokenService) -> dict[str, Any]:
    return jwt.decode(
        token_service.emitir(usuario(Rol.ADMIN)).access_token,
        options={"verify_signature": False},
    )


def test_alg_none(token_service: JwtTokenService) -> None:
    sin_firma = (
        f"{segmento({'alg': 'none', 'typ': 'JWT'})}.{segmento(_claims_validos(token_service))}."
    )

    with pytest.raises(TokenInvalidoError):
        token_service.verificar(sin_firma)


def test_hs256_firmado_con_la_llave_publica(
    llaves_rsa: LlavesRsa, token_service: JwtTokenService
) -> None:
    # Ataque de confusión de algoritmo: HMAC usando la llave pública (conocida) como secreto.
    header = segmento({"alg": "HS256", "typ": "JWT", "kid": token_service.kid})
    payload = segmento(_claims_validos(token_service))
    firma = hmac.new(llaves_rsa.public_pem, f"{header}.{payload}".encode(), hashlib.sha256)
    falsificado = f"{header}.{payload}.{b64url(firma.digest())}"

    with pytest.raises(TokenInvalidoError):
        token_service.verificar(falsificado)


@pytest.mark.parametrize("basura", ["", "abc", "a.b.c", "Bearer x.y.z"])
def test_tokens_mal_formados(token_service: JwtTokenService, basura: str) -> None:
    with pytest.raises(TokenInvalidoError) as exc_info:
        token_service.verificar(basura)

    assert exc_info.value.motivo == "invalido"


def test_jwks_expone_el_kid_y_sirve_para_verificar(token_service: JwtTokenService) -> None:
    emitido = token_service.emitir(usuario())

    [jwk] = token_service.jwks()["keys"]

    assert jwk["kid"] == jwt.get_unverified_header(emitido.access_token)["kid"]
    assert {k: jwk[k] for k in ("kty", "use", "alg")} == {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
    }
    assert set(jwk) == {"kty", "n", "e", "kid", "use", "alg"}  # nada de la parte privada
    llave = jwt.PyJWK(jwk).key
    payload = jwt.decode(emitido.access_token, llave, algorithms=["RS256"], issuer="iam-service")
    assert payload["jti"] == emitido.jti


def test_llaves_que_no_forman_par(llaves_rsa: LlavesRsa) -> None:
    _, otra_publica = generar_llaves_rsa()

    with pytest.raises(LlavesJwtError):
        JwtTokenService(
            llaves_rsa.private_pem,
            otra_publica,
            issuer="iam-service",
            ttl=timedelta(minutes=15),
            reloj=lambda: datetime.now(UTC),
        )
