from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_check_health
from app.api.schemas.health import HealthResponse, LiveResponse
from app.application.use_cases.check_health import CheckHealth

# Fuera del contrato público: son operativas y el gateway no las enruta.
router = APIRouter(tags=["health"], include_in_schema=False)


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    response: Response,
    check_health: Annotated[CheckHealth, Depends(get_check_health)],
) -> HealthResponse:
    """PostgreSQL y Valkey: lo consultan Prometheus y Blackbox para medir RNF-01 (C-32)."""
    report = await check_health.execute()
    if not report.healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if report.healthy else "degraded",
        checks={
            "database": "up" if report.database else "down",
            "valkey": "up" if report.cache else "down",
        },
    )


@router.get("/health/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    """Sin dependencias: readiness y liveness de Kubernetes y HEALTHCHECK de Docker (C-32)."""
    return LiveResponse()
