"""Métricas Prometheus del relay del outbox (las expone el worker en su propio puerto)."""

from prometheus_client import Counter, Gauge

EVENTOS_PUBLICADOS = Counter(
    "catalog_eventos_publicados_total",
    "Eventos del outbox confirmados por RabbitMQ.",
    ["event_type"],
)
FALLOS_PUBLICACION = Counter(
    "catalog_eventos_fallos_publicacion_total",
    "Envíos a RabbitMQ que no se confirmaron (el evento sigue pendiente).",
)
PENDIENTES = Gauge("catalog_outbox_pendientes", "Eventos del outbox sin publicar.")
ANTIGUEDAD = Gauge(
    "catalog_outbox_antiguedad_segundos",
    "Segundos que lleva esperando el evento pendiente más viejo (0 si no hay).",
)
