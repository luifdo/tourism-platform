"""Métrica Prometheus de las renovaciones de sesión (C-20), en /metrics de la API."""

from prometheus_client import Counter

# prometheus_client agrega el sufijo _total: se expone como iam_refresh_total.
RENOVACIONES = Counter(
    "iam_refresh",
    "Renovaciones de sesión por resultado (ok, invalido, revocado o reutilizado).",
    ["resultado"],
)
