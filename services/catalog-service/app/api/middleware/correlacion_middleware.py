import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id

CABECERA = "x-correlation-id"
# Solo se acepta un valor razonable del cliente; si no, se genera uno nuevo.
_VALIDO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class CorrelacionMiddleware:
    """Toma `X-Correlation-ID` (lo agrega Traefik) o lo genera, y lo devuelve en la respuesta.

    Es un middleware ASGI puro (no BaseHTTPMiddleware) para no penalizar la latencia de la
    búsqueda (ESC-02).
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        recibido = dict(scope["headers"]).get(CABECERA.encode(), b"").decode("latin-1")
        correlation_id = recibido if _VALIDO.match(recibido) else str(uuid4())
        fijar_correlation_id(correlation_id)

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                cabeceras = list(mensaje.get("headers", []))
                cabeceras.append((CABECERA.encode(), correlation_id.encode()))
                mensaje["headers"] = cabeceras
            await send(mensaje)

        await self._app(scope, receive, enviar)
