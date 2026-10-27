import logging
import sys

from app.infrastructure.observabilidad.formateador_json import FormateadorJson


def configurar_logs(servicio: str, nivel: str = "INFO") -> None:
    """Todos los logs (incluidos los de uvicorn) salen en JSON por stdout."""
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJson(servicio))
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel)
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(nombre)
        logger.handlers = []
        logger.propagate = True
