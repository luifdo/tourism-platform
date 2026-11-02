"""OUTBOX_EVENTOS_RETENIDOS (C-63): valor por defecto, comas, vacía y tipos desconocidos."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_sin_variable_retiene_usuario_suprimido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OUTBOX_EVENTOS_RETENIDOS", raising=False)

    assert settings().outbox_eventos_retenidos == ["usuario.suprimido"]


def test_vacia_no_retiene_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTBOX_EVENTOS_RETENIDOS", "")

    assert settings().outbox_eventos_retenidos == []


def test_separada_por_comas_sin_espacios_ni_repetidos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "OUTBOX_EVENTOS_RETENIDOS", " usuario.suprimido , prestador.aprobado,,usuario.suprimido"
    )

    assert settings().outbox_eventos_retenidos == ["usuario.suprimido", "prestador.aprobado"]


def test_un_tipo_desconocido_impide_arrancar(monkeypatch: pytest.MonkeyPatch) -> None:
    # Con un error de tipeo, el tipo real dejaría de retenerse sin que nadie lo note.
    monkeypatch.setenv("OUTBOX_EVENTOS_RETENIDOS", "usuario.suprimdo")

    with pytest.raises(ValidationError, match="usuario.suprimdo"):
        settings()
