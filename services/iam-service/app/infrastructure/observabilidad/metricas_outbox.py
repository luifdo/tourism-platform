"""Métricas Prometheus del relay del outbox (las expone el worker), como las de catalog."""

from prometheus_client import Counter, Gauge

EVENTOS_PUBLICADOS = Counter(
    "iam_eventos_publicados_total",
    "Eventos del outbox confirmados por RabbitMQ.",
    ["event_type"],
)
FALLOS_PUBLICACION = Counter(
    "iam_eventos_fallos_publicacion_total",
    "Envíos a RabbitMQ que no se confirmaron (el evento sigue pendiente).",
)
PENDIENTES = Gauge("iam_outbox_pendientes", "Eventos del outbox sin publicar.")
ANTIGUEDAD = Gauge(
    "iam_outbox_antiguedad_segundos",
    "Segundos que lleva esperando el evento pendiente más viejo (0 si no hay).",
)
