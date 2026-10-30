from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_check_health
from app.api.schemas.health import HealthResponse
from app.application.use_cases.check_health import CheckHealth

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    response: Response,
    check_health: Annotated[CheckHealth, Depends(get_check_health)],
) -> HealthResponse:
    report = await check_health.execute()
    if not report.healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if report.healthy else "degraded",
        checks={"database": "up" if report.database else "down"},
    )
