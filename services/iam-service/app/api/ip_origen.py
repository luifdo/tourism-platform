import ipaddress

from fastapi import Request


def ip_origen(request: Request) -> str | None:
    # uvicorn --proxy-headers ya pone aquí la IP real si viene de un proxy de confianza.
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        # Clientes que no reportan una IP (p. ej. "testclient"); la columna es INET.
        return None
