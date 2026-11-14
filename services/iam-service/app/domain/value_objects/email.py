import re
from dataclasses import dataclass

from app.domain.exceptions import EmailInvalidoError

MAX_LONGITUD = 254
# Validación básica local@dominio.tld; la estricta la hace Pydantic (EmailStr) en la capa HTTP.
_FORMATO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Email:
    """Correo normalizado: sin espacios a los lados y en minúsculas."""

    value: str

    def __post_init__(self) -> None:
        normalizado = self.value.strip().lower()
        if len(normalizado) > MAX_LONGITUD:
            raise EmailInvalidoError(
                f"El correo electrónico no puede superar {MAX_LONGITUD} caracteres."
            )
        if not _FORMATO.fullmatch(normalizado):
            raise EmailInvalidoError()
        object.__setattr__(self, "value", normalizado)

    def __str__(self) -> str:
        return self.value
