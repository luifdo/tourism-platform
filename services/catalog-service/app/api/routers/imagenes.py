from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_solicitar_subida_imagen
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.solicitud_imagen import SolicitudImagen
from app.api.schemas.subida_imagen_respuesta import SubidaImagenRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.application.use_cases.solicitar_subida_imagen import SolicitarSubidaImagen
from app.domain.value_objects.identidad import Identidad

router = APIRouter(prefix="/api/catalog/prestador", tags=["Prestador"])


@router.post(
    "/imagenes",
    summary="Pedir una URL de subida de imagen",
    status_code=status.HTTP_201_CREATED,
    response_model=SubidaImagenRespuesta,
    responses={code: {"model": ErrorRespuesta} for code in (400, 401, 403)},
)
async def solicitar_subida_imagen(
    identidad: Annotated[Identidad, Depends(identidad_peticion)],
    solicitud: SolicitudImagen,
    solicitar: Annotated[SolicitarSubidaImagen, Depends(get_solicitar_subida_imagen)],
) -> SubidaImagenRespuesta:
    subida = await solicitar.execute(identidad, solicitud.a_dominio())
    return SubidaImagenRespuesta.desde(subida)
