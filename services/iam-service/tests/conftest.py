from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings
from app.infrastructure.security.jwt_token_service import JwtTokenService


@dataclass(frozen=True)
class LlavesRsa:
    private_pem: bytes
    public_pem: bytes
    private_path: Path
    public_path: Path


def generar_llaves_rsa() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def llaves_rsa(tmp_path_factory: pytest.TempPathFactory) -> LlavesRsa:
    """Par RSA temporal: las pruebas nunca leen keys/."""
    private_pem, public_pem = generar_llaves_rsa()
    directorio = tmp_path_factory.mktemp("llaves")
    private_path = directorio / "private.pem"
    public_path = directorio / "public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return LlavesRsa(private_pem, public_pem, private_path, public_path)


@pytest.fixture(autouse=True)
def _settings_con_llaves_temporales(
    llaves_rsa: LlavesRsa, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    # Las variables de entorno tienen prioridad sobre el .env en pydantic-settings.
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", str(llaves_rsa.private_path))
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", str(llaves_rsa.public_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def crear_token_service(
    llaves: LlavesRsa, reloj: datetime | None = None, issuer: str = "iam-service"
) -> JwtTokenService:
    return JwtTokenService(
        llaves.private_pem,
        llaves.public_pem,
        issuer=issuer,
        ttl=timedelta(minutes=15),
        reloj=(lambda: reloj) if reloj is not None else (lambda: datetime.now(UTC)),
    )


@pytest.fixture
def token_service(llaves_rsa: LlavesRsa) -> JwtTokenService:
    return crear_token_service(llaves_rsa)
