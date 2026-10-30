from dataclasses import dataclass

from app.domain.exceptions import PasswordInvalidaError

MIN_LONGITUD = 8
MAX_LONGITUD = 128


@dataclass(frozen=True, repr=False)
class Password:
    """Contraseña en claro que cumple la política. Nunca se muestra en repr, str ni logs."""

    value: str

    def __post_init__(self) -> None:
        if not MIN_LONGITUD <= len(self.value) <= MAX_LONGITUD:
            raise PasswordInvalidaError()
        if not any(c.isalpha() for c in self.value) or not any(c.isdigit() for c in self.value):
            raise PasswordInvalidaError()

    def __repr__(self) -> str:
        return "Password(***)"

    def __str__(self) -> str:
        return "Password(***)"
