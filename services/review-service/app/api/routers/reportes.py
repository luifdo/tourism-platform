"""Reporte de reseñas inapropiadas (UC39): lo usan turistas y prestadores."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_reportar_resena
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.reporte_crear import ReporteCrear
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.application.use_cases.reportar_resena import ReportarResena
from app.domain.value_objects.identidad import Identidad

router = APIRouter(prefix="/api/reviews", tags=["Turista", "Prestador"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
_ERRORES = {codigo: {"model": ErrorRespuesta} for codigo in (400, 401, 403, 404, 409, 429)}


@router.post(
    "/resenas/{resena_id}/reportes",
    summary="Reportar una reseña inapropiada (UC39)",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORES,
)
async def reportar_resena(
    resena_id: UUID,
    identidad: IdentidadDep,
    datos: ReporteCrear,
    reportar: Annotated[ReportarResena, Depends(get_reportar_resena)],
) -> Response:
    await reportar.execute(identidad, resena_id, datos.motivo, datos.detalle)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
