"""Lecturas públicas: reseñas visibles y calificación de un servicio (sin identidad).

Las usan la ficha del servicio en la PWA y la tool `resenas_servicio` del Módulo 5.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import (
    get_listar_resenas_servicio,
    get_obtener_resena_publica,
    get_resumir_servicio,
)
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.comun import pagina_json
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.resena_publica_respuesta import ResenaPublicaRespuesta
from app.api.schemas.resumen_servicio_respuesta import ResumenServicioRespuesta
from app.application.dto.orden_resenas import OrdenResenas
from app.application.use_cases.listar_resenas_servicio import ListarResenasServicio
from app.application.use_cases.obtener_resena_publica import ObtenerResenaPublica
from app.application.use_cases.resumir_servicio import ResumirServicio
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/reviews", tags=["Público"])

IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]
Pagina = Annotated[int, Query(ge=1, le=10000)]
Tamano = Annotated[int, Query(ge=1, le=50)]
_ERRORES = {400: {"model": ErrorRespuesta}}


def _json(cuerpo: object, idioma: Idioma) -> JSONResponse:
    return JSONResponse(cuerpo, headers={"Content-Language": idioma.value})


@router.get(
    "/servicios/{servicio_id}/resenas",
    summary="Reseñas visibles de un servicio",
    responses=_ERRORES,
)
async def listar_resenas_servicio(
    servicio_id: UUID,
    idioma: IdiomaDep,
    listar: Annotated[ListarResenasServicio, Depends(get_listar_resenas_servicio)],
    orden: OrdenResenas = OrdenResenas.RECIENTES,
    pagina: Pagina = 1,
    tamano: Tamano = 20,
) -> Response:
    resultado = await listar.execute(servicio_id, orden, pagina, tamano)
    return _json(pagina_json(resultado, ResenaPublicaRespuesta, idioma), idioma)


@router.get(
    "/servicios/{servicio_id}/resumen",
    summary="Calificación de un servicio",
    response_model=ResumenServicioRespuesta,
    responses=_ERRORES,
)
async def resumen_servicio(
    servicio_id: UUID,
    resumir: Annotated[ResumirServicio, Depends(get_resumir_servicio)],
) -> ResumenServicioRespuesta:
    return ResumenServicioRespuesta.desde(await resumir.execute(servicio_id))


@router.get(
    "/resenas/{resena_id}",
    summary="Una reseña visible",
    response_model=ResenaPublicaRespuesta,
    responses=_ERRORES | {404: {"model": ErrorRespuesta}},
)
async def obtener_resena(
    resena_id: UUID,
    idioma: IdiomaDep,
    obtener: Annotated[ObtenerResenaPublica, Depends(get_obtener_resena_publica)],
) -> Response:
    resena = await obtener.execute(resena_id)
    return _json(ResenaPublicaRespuesta.desde(resena, idioma).a_json(), idioma)
