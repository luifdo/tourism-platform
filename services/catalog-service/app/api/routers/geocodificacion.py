from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_geocodificar
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.candidato_direccion_respuesta import CandidatoDireccionRespuesta
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.application.use_cases.geocodificar_direccion import GeocodificarDireccion
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Prestador"])


@router.get(
    "/geocodificar",
    summary="Sugerir coordenadas para una dirección",
    response_model=list[CandidatoDireccionRespuesta],
    responses={code: {"model": ErrorRespuesta} for code in (400, 401, 403, 503)},
)
async def geocodificar(
    identidad: Annotated[Identidad, Depends(identidad_peticion)],
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    geocodificar: Annotated[GeocodificarDireccion, Depends(get_geocodificar)],
    direccion: Annotated[str, Query(min_length=5, max_length=200)],
) -> list[CandidatoDireccionRespuesta]:
    candidatos = await geocodificar.execute(identidad, direccion, idioma)
    return [CandidatoDireccionRespuesta.desde(c) for c in candidatos]
