import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual


class FormateadorJson(logging.Formatter):
    """Una línea JSON por registro, con `correlation_id`, para que Loki siga una petición.

    Los campos estructurados se pasan con `extra={"campos": {...}}` y van al nivel superior
    del JSON (por ejemplo, `usuario_id` y `resultado` de la consulta de contacto).
    """

    def __init__(self, servicio: str) -> None:
        super().__init__()
        self._servicio = servicio

    def format(self, record: logging.LogRecord) -> str:
        registro: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "servicio": self._servicio,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "correlation_id": correlation_id_actual(),
        }
        campos = getattr(record, "campos", None)
        if isinstance(campos, dict):
            # Las claves fijas tienen prioridad: un campo no puede pisar ts, nivel, etc.
            registro |= {k: v for k, v in campos.items() if k not in registro}
        if record.exc_info:
            registro["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(registro, ensure_ascii=False, default=str)
