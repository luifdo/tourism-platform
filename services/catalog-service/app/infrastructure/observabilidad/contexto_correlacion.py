"""Identificador de correlación de la petición o el evento en curso (Plan §4.1, §7.5).

Vive en un ContextVar: cada petición asíncrona ve el suyo sin pasarlo por parámetros, y lo
leen los logs, las respuestas de error y (más adelante) los eventos publicados.
"""

from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def correlation_id_actual() -> str | None:
    return _correlation_id.get()


def fijar_correlation_id(valor: str) -> None:
    _correlation_id.set(valor)
