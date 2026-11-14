import pytest

from app.domain.exceptions import EmailInvalidoError, PasswordInvalidaError
from app.domain.value_objects.email import Email
from app.domain.value_objects.password import Password


def test_email_se_normaliza() -> None:
    assert Email("  Maria.Perez@Example.COM ").value == "maria.perez@example.com"


def test_email_iguales_tras_normalizar() -> None:
    assert Email("A@B.co") == Email("a@b.co")


def test_email_en_el_largo_maximo() -> None:
    email = "a" * 64 + "@" + "b" * 185 + ".com"
    assert len(email) == 254
    assert Email(email).value == email


def test_email_supera_el_largo_maximo() -> None:
    email = "a" * 64 + "@" + "b" * 186 + ".com"
    with pytest.raises(EmailInvalidoError):
        Email(email)


@pytest.mark.parametrize(
    "valor",
    ["", "   ", "sin-arroba.com", "a@b", "@b.com", "a@.com", "a b@c.com", "a@b@c.com"],
)
def test_email_con_formato_invalido(valor: str) -> None:
    with pytest.raises(EmailInvalidoError) as info:
        Email(valor)
    assert info.value.code == "EMAIL_INVALIDO"


@pytest.mark.parametrize("valor", ["abcdefg1", "Tayrona2026", "x" * 127 + "1"])
def test_password_valida(valor: str) -> None:
    assert Password(valor).value == valor


@pytest.mark.parametrize(
    "valor",
    [
        "abc123",  # muy corta
        "abcdef1",  # 7 caracteres
        "x" * 128 + "1",  # 129 caracteres
        "solamenteletras",
        "1234567890",
        "",
    ],
)
def test_password_invalida(valor: str) -> None:
    with pytest.raises(PasswordInvalidaError) as info:
        Password(valor)
    assert info.value.code == "PASSWORD_INVALIDA"


def test_password_en_los_limites() -> None:
    assert Password("abcdefg1")  # 8
    assert Password("x" * 127 + "1")  # 128


def test_password_nunca_muestra_su_valor() -> None:
    password = Password("Tayrona2026")

    assert "Tayrona2026" not in repr(password)
    assert "Tayrona2026" not in str(password)
    assert repr(password) == "Password(***)"
    assert str(password) == "Password(***)"
    assert "Tayrona2026" not in f"{password!r} {password}"
