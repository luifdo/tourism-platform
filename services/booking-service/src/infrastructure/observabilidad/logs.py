"""Logs en JSON por stdout, una línea por registro, para que Loki siga una petición."""

import json
import logging
import sys
from datetime import UTC, datetime

from infrastructure.observabilidad.correlacion import correlation_id_actual


class FormateadorJson(logging.Formatter):
    """Mismos campos que catalog-service: ts, nivel, servicio, logger, mensaje y correlation_id."""

    def __init__(self, servicio: str) -> None:
        super().__init__()
        self._servicio = servicio

    def format(self, record: logging.LogRecord) -> str:
        registro = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "servicio": self._servicio,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "correlation_id": correlation_id_actual(),
        }
        if record.exc_info:
            registro["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(registro, ensure_ascii=False)


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
