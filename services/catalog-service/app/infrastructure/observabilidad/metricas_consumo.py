"""Métricas Prometheus de los consumidores de eventos (las expone el worker)."""

from prometheus_client import Counter

EVENTOS_CONSUMIDOS = Counter(
    "catalog_eventos_consumidos_total",
    "Eventos recibidos por cola, tipo y resultado (aplicado, duplicado, ignorado, "
    "reintento o dlq).",
    ["cola", "event_type", "resultado"],
)
