"""Reseñas de los servicios del prestador (para responderlas en UC21)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_listar_resenas_prestador
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.comun import pagina_json
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.resena_prestador_respuesta import ResenaPrestadorRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.application.use_cases.listar_resenas_prestador import ListarResenasPrestador
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/reviews", tags=["Prestador"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]
_ERRORES = {
    400: {"model": ErrorRespuesta},
    401: {"model": ErrorRespuesta},
    403: {"model": ErrorRespuesta},
}


@router.get("/prestador/resenas", summary="Reseñas de mis servicios", responses=_ERRORES)
async def resenas_del_prestador(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    listar: Annotated[ListarResenasPrestador, Depends(get_listar_resenas_prestador)],
    servicio_id: UUID | None = None,
    sin_respuesta: bool = False,
    pagina: Annotated[int, Query(ge=1, le=10000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Response:
    resultado = await listar.execute(identidad, servicio_id, sin_respuesta, pagina, tamano)
    return JSONResponse(
        pagina_json(resultado, ResenaPrestadorRespuesta, idioma),
        headers={"Content-Language": idioma.value},
    )
