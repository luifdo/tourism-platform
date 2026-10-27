"""Sondas de Kubernetes y métricas de Prometheus (RNF-01).

`/metrics` lo genera prometheus-fastapi-instrumentator, igual que en catalog, iam y
recommendation: las mismas series (`http_requests_total`, `http_request_duration_seconds`,
etiquetadas por `handler`) sirven para un solo tablero de Grafana. Las métricas propias de
booking (eventos consumidos) se agregan al mismo registro para que salgan en el mismo `/metrics`.
"""

from typing import Literal

from fastapi import APIRouter, FastAPI, Request, Response, status
from prometheus_client import CollectorRegistry, Counter
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from infrastructure.persistence.db import verificar_conexion

router = APIRouter(tags=["Operación"])

EVENTOS_CONSUMIDOS = Counter(
    "booking_eventos_consumidos_total",
    "Mensajes consumidos de RabbitMQ por resultado (aplicado, descartado, reintento, dlq)",
    ["cola", "event_type", "resultado"],
    registry=None,  # se agrega al registro de cada app en registrar_metricas
)


class Salud(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, Literal["up", "down"]]


@router.get(
    "/health",
    response_model=Salud,
    summary="Estado del servicio (sondas de Kubernetes)",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Salud}},
)
async def health(request: Request, response: Response) -> Salud:
    """503 si la base no responde, para que Kubernetes deje de enviarle tráfico a esta réplica
    hasta que vuelva. RabbitMQ no cuenta: sin él las peticiones siguen y los eventos esperan en
    el outbox. En modo memoria no hay base."""
    motor = request.app.state.contenedor.extras.get("motor")
    checks = {"postgres": await verificar_conexion(motor)} if motor is not None else {"almacen_memoria": True}
    sano = all(checks.values())
    if not sano:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Salud(status="ok" if sano else "degraded", checks={k: "up" if v else "down" for k, v in checks.items()})


def registrar_metricas(app: FastAPI) -> None:
    # Un registro por app: si en el mismo proceso se crea otra (las pruebas lo hacen), la segunda
    # no queda sin métricas por encontrar ya registradas las de la primera. En el pod hay una sola.
    registro = CollectorRegistry()
    registro.register(EVENTOS_CONSUMIDOS)
    Instrumentator(registry=registro).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
