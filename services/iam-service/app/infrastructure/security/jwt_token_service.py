import base64
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.domain.entities.usuario import Usuario
from app.domain.exceptions import TokenInvalidoError
from app.domain.value_objects.enums import Rol
from app.domain.value_objects.token import ClaimsToken, TokenEmitido

ALGORITMO = "RS256"
LEEWAY_SEGUNDOS = 10
CLAIMS_OBLIGATORIOS = ["iss", "exp", "iat", "sub", "jti"]


class LlavesJwtError(RuntimeError):
    """Las llaves RS256 no existen, no se pueden leer o no forman un par."""


def leer_llaves(private_path: Path, public_path: Path) -> tuple[bytes, bytes]:
    for nombre, variable, path in (
        ("privada", "JWT_PRIVATE_KEY_PATH", private_path),
        ("pública", "JWT_PUBLIC_KEY_PATH", public_path),
    ):
        if not path.is_file():
            raise LlavesJwtError(
                f"No se encontró la llave {nombre} RS256 en '{path}' ({variable}). "
                "Genere el par con: openssl genpkey -algorithm RSA "
                "-pkeyopt rsa_keygen_bits:2048 -out keys/private.pem && "
                "openssl rsa -in keys/private.pem -pubout -out keys/public.pem"
            )
    return private_path.read_bytes(), public_path.read_bytes()


def _b64url_uint(valor: int) -> str:
    crudo = valor.to_bytes((valor.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode("ascii")


def _jwk_publica(public_key: RSAPublicKey) -> dict[str, str]:
    numeros = public_key.public_numbers()
    return {"kty": "RSA", "n": _b64url_uint(numeros.n), "e": _b64url_uint(numeros.e)}


def huella_rfc7638(public_key: RSAPublicKey) -> str:
    """Huella JWK (RFC 7638): SHA-256 de {e, kty, n} en orden y sin espacios, en base64url."""
    jwk = _jwk_publica(public_key)
    canonico = json.dumps({k: jwk[k] for k in ("e", "kty", "n")}, separators=(",", ":"))
    digest = hashlib.sha256(canonico.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _uuid_o_none(valor: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor))
    except ValueError:
        return None


class JwtTokenService:
    """Implementa TokenService con PyJWT y RS256."""

    def __init__(
        self,
        private_key_pem: bytes,
        public_key_pem: bytes,
        issuer: str,
        ttl: timedelta,
        reloj: Callable[[], datetime],
    ) -> None:
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        public_key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(private_key, RSAPrivateKey) or not isinstance(public_key, RSAPublicKey):
            raise LlavesJwtError("Las llaves JWT deben ser RSA (RS256).")
        if private_key.public_key().public_numbers() != public_key.public_numbers():
            raise LlavesJwtError("La llave pública no corresponde a la llave privada.")
        self._private_key = private_key
        self._public_key = public_key
        self._issuer = issuer
        self._ttl = ttl
        self._reloj = reloj
        self.kid = huella_rfc7638(public_key)

    def emitir(self, usuario: Usuario) -> TokenEmitido:
        # Los claims numéricos de JWT van en segundos enteros.
        iat = self._reloj().replace(microsecond=0)
        exp = iat + self._ttl
        jti = str(uuid.uuid4())
        claims = {
            "sub": str(usuario.id),
            "rol": usuario.rol.value,
            "jti": jti,
            "iat": iat,
            "exp": exp,
            "iss": self._issuer,
            "typ": "access",
        }
        token = jwt.encode(
            claims, self._private_key, algorithm=ALGORITMO, headers={"kid": self.kid}
        )
        return TokenEmitido(
            access_token=token,
            expires_in=int(self._ttl.total_seconds()),
            jti=jti,
            expira_en=exp,
        )

    def verificar(self, token: str) -> ClaimsToken:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[ALGORITMO],
                issuer=self._issuer,
                leeway=LEEWAY_SEGUNDOS,
                options={"require": CLAIMS_OBLIGATORIOS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenInvalidoError(
                motivo="expirado", usuario_id=self._sub_de_expirado(token)
            ) from exc
        except jwt.PyJWTError as exc:
            raise TokenInvalidoError(motivo="invalido") from exc

        # La firma ya es válida: desde aquí se conoce al usuario para la bitácora.
        if payload.get("typ") != "access":
            raise TokenInvalidoError(motivo="tipo", usuario_id=_uuid_o_none(payload["sub"]))
        try:
            return ClaimsToken(
                sub=payload["sub"],
                rol=Rol(payload["rol"]),
                jti=payload["jti"],
                iat=datetime.fromtimestamp(payload["iat"], UTC),
                exp=datetime.fromtimestamp(payload["exp"], UTC),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise TokenInvalidoError(motivo="invalido") from exc

    def _sub_de_expirado(self, token: str) -> uuid.UUID | None:
        # Solo para la bitácora: se omite exp pero la firma y el emisor se siguen verificando,
        # así que el sub es confiable. Si algo más falla, el intento queda sin usuario.
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[ALGORITMO],
                issuer=self._issuer,
                options={"verify_exp": False},
            )
        except jwt.PyJWTError:
            return None
        return _uuid_o_none(payload.get("sub"))

    def jwks(self) -> dict[str, list[dict[str, Any]]]:
        jwk = {**_jwk_publica(self._public_key), "kid": self.kid, "use": "sig", "alg": ALGORITMO}
        return {"keys": [jwk]}
