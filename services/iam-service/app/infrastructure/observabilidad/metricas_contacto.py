"""Métrica Prometheus de la ruta interna de contacto (C-15), que expone la API en /metrics."""

from prometheus_client import Counter

CONSULTAS_CONTACTO = Counter(
    "iam_contacto_consultas_total",
    "Consultas a /internal/usuarios/{id}/contacto por resultado "
    "(ok, no_encontrado o rechazado_proxy).",
    ["resultado"],
)
