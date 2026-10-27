"""Intención de visita ("Cómo llegar"): registro público y conteos para la Entidad."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.dependencies import get_listar_intenciones_visita, get_registrar_intencion_visita
from app.api.routers.parametros import Fecha
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.intenciones_zona_dia_respuesta import IntencionesZonaDiaRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.ip_origen import ip_origen
from app.application.dto.rango_fechas import RangoFechas
from app.application.use_cases.listar_intenciones_visita import ListarIntencionesVisita
from app.application.use_cases.registrar_intencion_visita import RegistrarIntencionVisita
from app.domain.value_objects.identidad import Identidad

router = APIRouter(prefix="/api/catalog")


@router.post(
    "/servicios/{servicio_id}/intencion-visita",
    summary='Registrar una intención de visita ("Cómo llegar")',
    tags=["Mapa"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorRespuesta}},
)
async def registrar_intencion_visita(
    servicio_id: UUID,
    request: Request,
    registrar: Annotated[RegistrarIntencionVisita, Depends(get_registrar_intencion_visita)],
) -> Response:
    await registrar.execute(servicio_id, ip_origen(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/analitica/intenciones-visita",
    summary='Intenciones de visita ("Cómo llegar") por zona y día',
    tags=["Analítica"],
    response_model=list[IntencionesZonaDiaRespuesta],
    responses={
        400: {"model": ErrorRespuesta},
        401: {"model": ErrorRespuesta},
        403: {"model": ErrorRespuesta},
    },
)
async def intenciones_visita(
    identidad: Annotated[Identidad, Depends(identidad_peticion)],
    listar: Annotated[ListarIntencionesVisita, Depends(get_listar_intenciones_visita)],
    desde: Fecha,
    hasta: Fecha,
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
) -> list[IntencionesZonaDiaRespuesta]:
    filas = await listar.execute(identidad, RangoFechas(desde, hasta), zona)
    return [IntencionesZonaDiaRespuesta.desde(f) for f in filas]
