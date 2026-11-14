"""Administración de alertas oficiales por la Entidad y el Admin (UC26)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import (
    RelojDep,
    get_editar_alerta,
    get_listar_alertas_entidad,
    get_publicar_alerta,
    get_retirar_alerta,
)
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.routers.parametros import Pagina
from app.api.schemas.alerta_crear import AlertaCrear
from app.api.schemas.alerta_editable_respuesta import AlertaEditableRespuesta
from app.api.schemas.alerta_editar import AlertaEditar
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.pagina_alertas_entidad_respuesta import PaginaAlertasEntidadRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.version_if_match import etag, version_if_match
from app.application.dto.alerta_editable import AlertaEditable
from app.application.dto.estado_alerta import EstadoAlerta
from app.application.use_cases.editar_alerta import EditarAlerta
from app.application.use_cases.listar_alertas_entidad import ListarAlertasEntidad
from app.application.use_cases.publicar_alerta import PublicarAlerta
from app.application.use_cases.retirar_alerta import RetirarAlerta
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.identidad import Identidad
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Entidad"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]

_ERRORES = {
    400: {"model": ErrorRespuesta},
    401: {"model": ErrorRespuesta},
    403: {"model": ErrorRespuesta},
    404: {"model": ErrorRespuesta},
}


def _respuesta(
    editable: AlertaEditable, idioma: Idioma, reloj: RelojDep, estado: int = status.HTTP_200_OK
) -> JSONResponse:
    cuerpo = AlertaEditableRespuesta.desde(editable, idioma, reloj.ahora())
    return JSONResponse(
        cuerpo.model_dump(mode="json"),
        status_code=estado,
        headers={"ETag": etag(cuerpo.version), "Content-Language": idioma.value},
    )


@router.post(
    "/alertas",
    summary="Publicar una alerta oficial (UC26)",
    status_code=status.HTTP_201_CREATED,
    response_model=AlertaEditableRespuesta,
    responses=_ERRORES,
)
async def publicar_alerta(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    reloj: RelojDep,
    datos: AlertaCrear,
    publicar: Annotated[PublicarAlerta, Depends(get_publicar_alerta)],
) -> Response:
    editable = await publicar.execute(
        identidad,
        datos.nivel,
        datos.mensaje.a_dominio(),
        datos.fecha_expiracion,
        datos.servicio_id,
        CodigoZona(datos.zona) if datos.zona is not None else None,
    )
    return _respuesta(editable, idioma, reloj, status.HTTP_201_CREATED)


@router.put(
    "/alertas/{alerta_id}",
    summary="Editar una alerta oficial vigente (UC26)",
    response_model=AlertaEditableRespuesta,
    responses=_ERRORES | {409: {"model": ErrorRespuesta}, 428: {"model": ErrorRespuesta}},
)
async def editar_alerta(
    alerta_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    reloj: RelojDep,
    version: Annotated[int, Depends(version_if_match)],
    datos: AlertaEditar,
    editar: Annotated[EditarAlerta, Depends(get_editar_alerta)],
) -> Response:
    editable = await editar.execute(
        identidad,
        alerta_id,
        version,
        datos.nivel,
        datos.mensaje.a_dominio(),
        datos.fecha_expiracion,
    )
    return _respuesta(editable, idioma, reloj)


@router.post(
    "/alertas/{alerta_id}/desactivar",
    summary="Retirar una alerta oficial (UC26)",
    response_model=AlertaEditableRespuesta,
    responses=_ERRORES,
)
async def retirar_alerta(
    alerta_id: UUID,
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    reloj: RelojDep,
    retirar: Annotated[RetirarAlerta, Depends(get_retirar_alerta)],
) -> Response:
    return _respuesta(await retirar.execute(identidad, alerta_id), idioma, reloj)


@router.get(
    "/entidad/alertas",
    summary="Panel de alertas de la Entidad (UC26)",
    response_model=PaginaAlertasEntidadRespuesta,
    responses=_ERRORES,
)
async def alertas_de_la_entidad(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    listar: Annotated[ListarAlertasEntidad, Depends(get_listar_alertas_entidad)],
    estado: EstadoAlerta | None = None,
    pagina: Pagina = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginaAlertasEntidadRespuesta:
    resultado = await listar.execute(identidad, estado, pagina, tamano)
    return PaginaAlertasEntidadRespuesta.desde(resultado, idioma)
