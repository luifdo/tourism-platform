from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from src.application.verificar_salud import VerificarSalud
from src.infrastructure.http.dependencias import obtener_verificar_salud

router = APIRouter(tags=["Operación"])


def _estado(responde: bool) -> str:
    return "up" if responde else "down"


@router.get("/health")
async def health(
    response: Response,
    verificar_salud: Annotated[VerificarSalud, Depends(obtener_verificar_salud)],
) -> dict[str, object]:
    """Sonda de Kubernetes: 200 si PostgreSQL y Valkey responden, 503 si alguno no."""
    estado = await verificar_salud.ejecutar()
    if not estado.sano:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if estado.sano else "degraded",
        "checks": {"database": _estado(estado.base_de_datos), "valkey": _estado(estado.valkey)},
    }
