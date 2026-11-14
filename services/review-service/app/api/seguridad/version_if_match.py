"""Concurrencia optimista por HTTP: `ETag: "3"` al leer, `If-Match: "3"` al editar."""

from typing import Annotated

from fastapi import Header

from app.application.errores import FaltaIfMatch
from app.domain.errors import DatoInvalido


def etag(version: int) -> str:
    return f'"{version}"'


def version_if_match(
    if_match: Annotated[
        str | None, Header(description="Versión (`ETag`) que el usuario tenía al editar")
    ] = None,
) -> int:
    """Acepta `"3"`, `W/"3"` o `3` (algunos clientes quitan las comillas)."""
    if if_match is None or not if_match.strip():
        raise FaltaIfMatch()
    valor = if_match.strip().removeprefix("W/").strip('"')
    if not valor.isdigit() or int(valor) < 1:
        raise DatoInvalido(campo="If-Match", regla="formato")
    return int(valor)
