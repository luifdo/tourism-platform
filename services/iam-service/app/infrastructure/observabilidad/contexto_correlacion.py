"""Identificador de correlación de la petición o el evento en curso (Plan §4.1, §7.5).

Vive en un ContextVar: cada petición asíncrona ve el suyo sin pasarlo por parámetros. Lo fijan
el consumidor de eventos (con el del sobre) y CorrelacionMiddleware en la API (con
`X-Correlation-ID`). Lo leen la bitácora (`correlation_id`, C-05), las respuestas de error
(C-12) y los logs en JSON.
"""

from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def correlation_id_actual() -> str | None:
    return _correlation_id.get()


def fijar_correlation_id(valor: str | None) -> None:
    _correlation_id.set(valor)
