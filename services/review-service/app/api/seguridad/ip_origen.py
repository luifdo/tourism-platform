"""IP del cliente según Traefik.

Traefik pone el IP real en `X-Forwarded-For` y descarta el que mande el cliente si no viene
de un proxy de confianza (`forwardedHeaders.trustedIPs`); por eso se toma el primero. Sin
gateway (desarrollo), se usa el de la conexión.
"""

from fastapi import Request


def ip_origen(request: Request) -> str | None:
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip() or None
    return request.client.host if request.client else None
