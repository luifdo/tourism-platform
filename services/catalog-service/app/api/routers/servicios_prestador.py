"""Escritura de ofertas por su prestador (UC17, UC18) y su panel."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import (
    get_cambiar_estado_servicio,
    get_editar_servicio,
    get_idempotencia,
    get_listar_servicios_prestador,
    get_registrar_servicio,
)
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.routers.parametros import Pagina
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.pagina_servicios_editables_respuesta import (
    PaginaServiciosEditablesRespuesta,
)
from app.api.schemas.servicio_editable_respuesta import ServicioEditableRespuesta
from app.api.schemas.servicio_guardar import ServicioGuardar
from app.api.seguridad.idempotencia import responder_idempotente
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.version_if_match import etag, version_if_match
from app.application.dto.servicio_editable import ServicioEditable
from app.application.ports.almacen_idempotencia import AlmacenIdempotencia
from app.application.use_cases.cambiar_estado_servicio import (
    CambiarEstadoServicio,
    EstadoServicio,
)
from app.application.use_cases.editar_servicio import EditarServicio
from app.application.use_cases.listar_servicios_prestador import ListarServiciosPrestador
from app.application.use_cases.registrar_servicio import RegistrarServicio
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Prestador"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]
VersionDep = Annotated[int, Depends(version_if_match)]
Idempotencia = Annotated[AlmacenIdempotencia, Depends(get_idempotencia)]
ClaveIdempotencia = Annotated[UUID | None, Header(alias="Idempotency-Key")]

_ERRORES = {
    400: {"model": ErrorRespuesta},
    401: {"model": ErrorRespuesta},
    403: {"model": ErrorRespuesta},
}
_ERRORES_EDICION = _ERRORES | {
    404: {"model": ErrorRespuesta},
    409: {"model": ErrorRespuesta},
    428: {"model": ErrorRespuesta},
}


def _respuesta(editable: ServicioEditable, idioma: Idioma, estado: int = 200) -> JSONResponse:
    cuerpo = ServicioEditableRespuesta.desde(editable, idioma)
    return JSONResponse(
        cuerpo.model_dump(mode="json"),
        status_code=estado,
        headers={"ETag": etag(cuerpo.version), "Content-Language": idioma.value},
    )


@router.post(
    "/servicios",
    summary="Registrar una oferta (UC17)",
    status_code=status.HTTP_201_CREATED,
    response_model=ServicioEditableRespuesta,
    responses=_ERRORES,
)
async def registrar_servicio(
    request: Request,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    datos: ServicioGuardar,
    registrar: Annotated[RegistrarServicio, Depends(get_registrar_servicio)],
    idempotencia: Idempotencia,
    clave: ClaveIdempotencia = None,
) -> Response:
    async def ejecutar() -> JSONResponse:
        editable = await registrar.execute(identidad, datos.a_dominio())
        return _respuesta(editable, idioma, status.HTTP_201_CREATED)

    return await responder_idempotente(idempotencia, request, identidad, clave, ejecutar)


@router.put(
    "/servicios/{servicio_id}",
    summary="Editar una oferta (UC18)",
    response_model=ServicioEditableRespuesta,
    responses=_ERRORES_EDICION,
)
async def editar_servicio(
    request: Request,
    servicio_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    version: VersionDep,
    datos: ServicioGuardar,
    editar: Annotated[EditarServicio, Depends(get_editar_servicio)],
    idempotencia: Idempotencia,
    clave: ClaveIdempotencia = None,
) -> Response:
    async def ejecutar() -> JSONResponse:
        editable = await editar.execute(identidad, servicio_id, version, datos.a_dominio())
        return _respuesta(editable, idioma)

    return await responder_idempotente(idempotencia, request, identidad, clave, ejecutar)


@router.post(
    "/servicios/{servicio_id}/desactivar",
    summary="Desactivar una oferta (UC18)",
    response_model=ServicioEditableRespuesta,
    responses=_ERRORES_EDICION,
)
async def desactivar_servicio(
    servicio_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    version: VersionDep,
    cambiar: Annotated[CambiarEstadoServicio, Depends(get_cambiar_estado_servicio)],
) -> Response:
    editable = await cambiar.execute(identidad, servicio_id, version, EstadoServicio.INACTIVO)
    return _respuesta(editable, idioma)


@router.post(
    "/servicios/{servicio_id}/reactivar",
    summary="Reactivar una oferta (UC18)",
    response_model=ServicioEditableRespuesta,
    responses=_ERRORES_EDICION,
)
async def reactivar_servicio(
    servicio_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    version: VersionDep,
    cambiar: Annotated[CambiarEstadoServicio, Depends(get_cambiar_estado_servicio)],
) -> Response:
    editable = await cambiar.execute(identidad, servicio_id, version, EstadoServicio.ACTIVO)
    return _respuesta(editable, idioma)


@router.get(
    "/prestador/servicios",
    summary="Servicios del prestador autenticado (UC18)",
    response_model=PaginaServiciosEditablesRespuesta,
    responses=_ERRORES,
)
async def servicios_del_prestador(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    listar: Annotated[ListarServiciosPrestador, Depends(get_listar_servicios_prestador)],
    pagina: Pagina = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginaServiciosEditablesRespuesta:
    resultado = await listar.execute(identidad, pagina, tamano)
    return PaginaServiciosEditablesRespuesta.desde(resultado, idioma)
