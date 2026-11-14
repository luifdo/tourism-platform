"""Moderación del Administrador (UC29): la cola y la decisión sobre cada reseña."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_listar_cola_moderacion, get_moderar_resena
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.decision_moderacion_datos import DecisionModeracionDatos
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.resena_moderacion_respuesta import ResenaModeracionRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.ip_origen import ip_origen
from app.api.seguridad.version_if_match import etag, version_if_match
from app.application.dto.resena_en_moderacion import ResenaEnModeracion
from app.application.use_cases.listar_cola_moderacion import ListarColaModeracion
from app.application.use_cases.moderar_resena import ModerarResena
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/reviews", tags=["Moderación"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]
VersionDep = Annotated[int, Depends(version_if_match)]
_ERRORES = {codigo: {"model": ErrorRespuesta} for codigo in (400, 401, 403)}
_ERRORES_DECISION = _ERRORES | {codigo: {"model": ErrorRespuesta} for codigo in (404, 409, 428)}


@router.get("/moderacion/resenas", summary="Cola de moderación (UC29)", responses=_ERRORES)
async def cola_moderacion(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    listar: Annotated[ListarColaModeracion, Depends(get_listar_cola_moderacion)],
    estado: EstadoResena | None = None,
    pagina: Annotated[int, Query(ge=1, le=10000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Response:
    resultado = await listar.execute(identidad, estado, pagina, tamano)
    cuerpo = {
        "items": [
            ResenaModeracionRespuesta.de_moderacion(i, idioma).a_json() for i in resultado.items
        ],
        "pagina": resultado.pagina,
        "tamano": resultado.tamano,
        "total": resultado.total,
    }
    return JSONResponse(cuerpo, headers={"Content-Language": idioma.value})


@router.post(
    "/resenas/{resena_id}/moderacion",
    summary="Decidir sobre una reseña reportada (UC29)",
    response_model=ResenaModeracionRespuesta,
    responses=_ERRORES_DECISION,
)
async def moderar_resena(
    request: Request,
    resena_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    version: VersionDep,
    datos: DecisionModeracionDatos,
    moderar: Annotated[ModerarResena, Depends(get_moderar_resena)],
) -> Response:
    resena = await moderar.execute(
        identidad, resena_id, version, datos.decision, datos.motivo, ip_origen(request)
    )
    # Tras decidir, los reportes quedan resueltos: la lista sale vacía.
    vista = ResenaModeracionRespuesta.de_moderacion(ResenaEnModeracion(resena, []), idioma)
    return JSONResponse(
        vista.a_json(),
        headers={"ETag": etag(resena.version), "Content-Language": idioma.value},
    )
