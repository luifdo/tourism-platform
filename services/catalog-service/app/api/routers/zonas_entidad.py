"""Administración de zonas por la Entidad y el Admin."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import (
    get_crear_zona,
    get_desactivar_zona,
    get_editar_zona,
    get_obtener_zona,
)
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.zona_editable_respuesta import ZonaEditableRespuesta
from app.api.schemas.zona_guardar import ZonaGuardar
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.version_if_match import etag, version_if_match
from app.application.use_cases.crear_zona import CrearZona
from app.application.use_cases.desactivar_zona import DesactivarZona
from app.application.use_cases.editar_zona import EditarZona
from app.application.use_cases.obtener_zona import ObtenerZona
from app.domain.entities.zona import Zona
from app.domain.value_objects.identidad import Identidad

router = APIRouter(prefix="/api/catalog/zonas", tags=["Entidad"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
VersionDep = Annotated[int, Depends(version_if_match)]

_ERRORES = {401: {"model": ErrorRespuesta}, 403: {"model": ErrorRespuesta}}
_ERRORES_EDICION = _ERRORES | {
    400: {"model": ErrorRespuesta},
    404: {"model": ErrorRespuesta},
    409: {"model": ErrorRespuesta},
    428: {"model": ErrorRespuesta},
}


def _respuesta(zona: Zona, estado: int = status.HTTP_200_OK) -> JSONResponse:
    cuerpo = ZonaEditableRespuesta.desde(zona)
    return JSONResponse(
        cuerpo.model_dump(mode="json"), status_code=estado, headers={"ETag": etag(zona.version)}
    )


@router.post(
    "",
    summary="Crear una zona",
    status_code=status.HTTP_201_CREATED,
    response_model=ZonaEditableRespuesta,
    responses=_ERRORES | {400: {"model": ErrorRespuesta}, 409: {"model": ErrorRespuesta}},
)
async def crear_zona(
    identidad: IdentidadDep,
    datos: ZonaGuardar,
    crear: Annotated[CrearZona, Depends(get_crear_zona)],
) -> Response:
    zona = await crear.execute(identidad, *datos.a_dominio())
    return _respuesta(zona, status.HTTP_201_CREATED)


@router.get(
    "/{zona_id}",
    summary="Detalle editable de una zona",
    response_model=ZonaEditableRespuesta,
    responses=_ERRORES | {404: {"model": ErrorRespuesta}},
)
async def obtener_zona(
    zona_id: UUID,
    identidad: IdentidadDep,
    obtener: Annotated[ObtenerZona, Depends(get_obtener_zona)],
) -> Response:
    return _respuesta(await obtener.execute(identidad, zona_id))


@router.put(
    "/{zona_id}",
    summary="Editar una zona",
    response_model=ZonaEditableRespuesta,
    responses=_ERRORES_EDICION,
)
async def editar_zona(
    zona_id: UUID,
    identidad: IdentidadDep,
    version: VersionDep,
    datos: ZonaGuardar,
    editar: Annotated[EditarZona, Depends(get_editar_zona)],
) -> Response:
    return _respuesta(await editar.execute(identidad, zona_id, version, *datos.a_dominio()))


@router.post(
    "/{zona_id}/desactivar",
    summary="Desactivar una zona",
    response_model=ZonaEditableRespuesta,
    responses=_ERRORES_EDICION,
)
async def desactivar_zona(
    zona_id: UUID,
    identidad: IdentidadDep,
    version: VersionDep,
    desactivar: Annotated[DesactivarZona, Depends(get_desactivar_zona)],
) -> Response:
    return _respuesta(await desactivar.execute(identidad, zona_id, version))
