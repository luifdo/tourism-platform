"""Perfil comercial del prestador autenticado (UC4 para prestadores)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_editar_perfil, get_idempotencia, get_obtener_perfil
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.perfil_editable_respuesta import PerfilEditableRespuesta
from app.api.schemas.perfil_guardar import PerfilGuardar
from app.api.seguridad.idempotencia import responder_idempotente
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.version_if_match import etag, version_if_match
from app.application.ports.almacen_idempotencia import AlmacenIdempotencia
from app.application.use_cases.editar_perfil import EditarPerfil
from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.identidad import Identidad

router = APIRouter(prefix="/api/catalog/prestador", tags=["Prestador"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
_ERRORES = {401: {"model": ErrorRespuesta}, 403: {"model": ErrorRespuesta}}


def _respuesta(perfil: PrestadorPerfil) -> JSONResponse:
    cuerpo = PerfilEditableRespuesta.desde(perfil)
    return JSONResponse(cuerpo.model_dump(mode="json"), headers={"ETag": etag(perfil.version)})


@router.get(
    "/perfil",
    summary="Perfil comercial del prestador autenticado",
    response_model=PerfilEditableRespuesta,
    responses=_ERRORES,
)
async def obtener_perfil(
    identidad: IdentidadDep,
    obtener: Annotated[ObtenerPerfil, Depends(get_obtener_perfil)],
) -> Response:
    return _respuesta(await obtener.execute(identidad))


@router.put(
    "/perfil",
    summary="Editar el perfil comercial",
    response_model=PerfilEditableRespuesta,
    responses=_ERRORES
    | {
        400: {"model": ErrorRespuesta},
        409: {"model": ErrorRespuesta},
        428: {"model": ErrorRespuesta},
    },
)
async def editar_perfil(
    request: Request,
    identidad: IdentidadDep,
    version: Annotated[int, Depends(version_if_match)],
    datos: PerfilGuardar,
    editar: Annotated[EditarPerfil, Depends(get_editar_perfil)],
    idempotencia: Annotated[AlmacenIdempotencia, Depends(get_idempotencia)],
    clave: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    async def ejecutar() -> JSONResponse:
        politica = datos.politica_cancelacion.a_dominio() if datos.politica_cancelacion else None
        perfil = await editar.execute(
            identidad, version, datos.telefono or None, datos.direccion or None, politica
        )
        return _respuesta(perfil)

    return await responder_idempotente(idempotencia, request, identidad, clave, ejecutar)
