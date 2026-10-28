"""Reseñas del turista: escribir y editar la propia (UC15)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_editar_resena, get_escribir_resena, get_idempotencia
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.resena_crear import ResenaCrear
from app.api.schemas.resena_guardar import ResenaGuardar
from app.api.schemas.resena_propia_respuesta import ResenaPropiaRespuesta
from app.api.seguridad.idempotencia import responder_idempotente
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.version_if_match import etag, version_if_match
from app.application.ports.almacen_idempotencia import AlmacenIdempotencia
from app.application.use_cases.editar_resena import EditarResena
from app.application.use_cases.escribir_resena import EscribirResena
from app.domain.entities.resena import Resena
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/reviews", tags=["Turista"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]
VersionDep = Annotated[int, Depends(version_if_match)]
Idempotencia = Annotated[AlmacenIdempotencia, Depends(get_idempotencia)]
ClaveIdempotencia = Annotated[UUID | None, Header(alias="Idempotency-Key")]

_ERRORES = {
    400: {"model": ErrorRespuesta},
    401: {"model": ErrorRespuesta},
    403: {"model": ErrorRespuesta},
    409: {"model": ErrorRespuesta},
}
_ERRORES_EDICION = _ERRORES | {404: {"model": ErrorRespuesta}, 428: {"model": ErrorRespuesta}}


def _respuesta(resena: Resena, idioma: Idioma, estado: int = status.HTTP_200_OK) -> JSONResponse:
    cuerpo = ResenaPropiaRespuesta.desde(resena, idioma)
    return JSONResponse(
        cuerpo.a_json(),
        status_code=estado,
        headers={"ETag": etag(resena.version), "Content-Language": idioma.value},
    )


@router.post(
    "/resenas",
    summary="Escribir una reseña (UC15)",
    status_code=status.HTTP_201_CREATED,
    response_model=ResenaPropiaRespuesta,
    responses=_ERRORES,
)
async def escribir_resena(
    request: Request,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    datos: ResenaCrear,
    escribir: Annotated[EscribirResena, Depends(get_escribir_resena)],
    idempotencia: Idempotencia,
    clave: ClaveIdempotencia = None,
) -> Response:
    async def ejecutar() -> JSONResponse:
        resena = await escribir.execute(identidad, datos.servicio_id, datos.a_dominio())
        return _respuesta(resena, idioma, status.HTTP_201_CREATED)

    return await responder_idempotente(idempotencia, request, identidad, clave, ejecutar)


@router.put(
    "/resenas/{resena_id}",
    summary="Editar mi reseña (UC15)",
    response_model=ResenaPropiaRespuesta,
    responses=_ERRORES_EDICION,
)
async def editar_resena(
    resena_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    version: VersionDep,
    datos: ResenaGuardar,
    editar: Annotated[EditarResena, Depends(get_editar_resena)],
) -> Response:
    resena = await editar.execute(identidad, resena_id, version, datos.a_dominio())
    return _respuesta(resena, idioma)
