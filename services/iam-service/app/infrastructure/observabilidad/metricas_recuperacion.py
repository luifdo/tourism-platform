"""Métrica Prometheus de las solicitudes de recuperación (C-28, C-50), en /metrics de la API."""

from prometheus_client import Counter

SOLICITUDES_RECUPERACION = Counter(
    "iam_recuperacion_solicitudes_total",
    "Solicitudes de recuperación de contraseña por resultado (enviado, no_elegible, "
    "enfriamiento, fallo_valkey, fallo_smtp o fallo_base).",
    ["resultado"],
)
