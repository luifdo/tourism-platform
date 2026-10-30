"""Métricas de la oferta del prestador autenticado (UC22)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_obtener_metricas_prestador
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.routers.parametros import Fecha
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.metricas_prestador_respuesta import MetricasPrestadorRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.application.dto.rango_fechas import RangoFechas
from app.application.use_cases.obtener_metricas_prestador import ObtenerMetricasPrestador
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog/prestador", tags=["Prestador"])


@router.get(
    "/metricas",
    summary="Métricas de la oferta del prestador (UC22)",
    response_model=MetricasPrestadorRespuesta,
    responses={
        400: {"model": ErrorRespuesta},
        401: {"model": ErrorRespuesta},
        403: {"model": ErrorRespuesta},
    },
)
async def metricas_prestador(
    identidad: Annotated[Identidad, Depends(identidad_peticion)],
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    obtener: Annotated[ObtenerMetricasPrestador, Depends(get_obtener_metricas_prestador)],
    desde: Fecha,
    hasta: Fecha,
) -> MetricasPrestadorRespuesta:
    metricas = await obtener.execute(identidad, RangoFechas(desde, hasta))
    return MetricasPrestadorRespuesta.desde_dto(metricas, idioma)
