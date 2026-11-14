"""Identificador de correlación de la petición en curso (Plan §4.1, §7.5).

Vive en un ContextVar: cada petición asíncrona ve el suyo sin pasarlo por parámetros, y lo
leen los logs, las respuestas de error y los eventos publicados. Mismo criterio que catalog-service.
"""

import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CABECERA = "x-correlation-id"
# Solo se acepta un valor razonable del cliente; si no, se genera uno nuevo.
_VALIDO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def correlation_id_actual() -> str | None:
    return _correlation_id.get()


def fijar_correlation_id(valor: str) -> None:
    _correlation_id.set(valor)


class CorrelacionMiddleware:
    """Toma `X-Correlation-ID` (lo agrega Traefik) o lo genera, y lo devuelve en la respuesta.

    Middleware ASGI puro (no BaseHTTPMiddleware) para no sumar latencia a las solicitudes.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        recibido = dict(scope["headers"]).get(CABECERA.encode(), b"").decode("latin-1")
        correlation_id = recibido if _VALIDO.match(recibido) else f"corr-{uuid4()}"
        fijar_correlation_id(correlation_id)

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                cabeceras = list(mensaje.get("headers", []))
                cabeceras.append((CABECERA.encode(), correlation_id.encode()))
                mensaje["headers"] = cabeceras
            await send(mensaje)

        await self._app(scope, receive, enviar)
