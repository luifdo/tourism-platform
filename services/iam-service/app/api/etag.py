"""Concurrencia optimista por HTTP (C-49): `ETag: "3"` al leer, `If-Match: "3"` al editar."""

from typing import Annotated

from fastapi import Header

from app.domain.exceptions import VersionConflictoError


def etag(version: int) -> str:
    return f'"{version}"'


def version_if_match(if_match: Annotated[str | None, Header()] = None) -> int | None:
    """Versión que el cliente tenía. None si no envió If-Match o envió `*`.

    Acepta `"3"`, `W/"3"` o `3` (algunos clientes quitan las comillas), como catalog. Cualquier
    otro valor no coincide con ninguna versión: 409.
    """
    if if_match is None or not if_match.strip() or if_match.strip() == "*":
        return None
    valor = if_match.strip().removeprefix("W/").strip('"')
    if not valor.isdecimal():
        raise VersionConflictoError()
    return int(valor)
