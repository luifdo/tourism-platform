import json
import logging
from datetime import UTC, datetime

from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual


class FormateadorJson(logging.Formatter):
    """Una línea JSON por registro, con `correlation_id`, para que Loki siga una petición."""

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
