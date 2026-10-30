from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_buscar_servicios, get_obtener_servicio
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.routers.parametros import Pagina
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.pagina_servicios_respuesta import PaginaServiciosRespuesta
from app.api.schemas.servicio_detalle_respuesta import ServicioDetalleRespuesta
from app.application.dto.criterios_busqueda import CriteriosBusqueda
from app.application.use_cases.buscar_servicios import BuscarServicios
from app.application.use_cases.obtener_servicio import ObtenerServicio
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Catálogo"])


@router.get(
    "/servicios",
    summary="Listar el catálogo (UC7)",
    response_model=PaginaServiciosRespuesta,
    responses={400: {"model": ErrorRespuesta}},
)
async def listar_servicios(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    buscar: Annotated[BuscarServicios, Depends(get_buscar_servicios)],
    categoria: Annotated[Categoria | None, Query()] = None,
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
    pagina: Pagina = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginaServiciosRespuesta:
    criterios = CriteriosBusqueda(
        idioma=idioma,
        pagina=pagina,
        tamano=tamano,
        categorias=(categoria,) if categoria else (),
        zona=zona,
    )
    return PaginaServiciosRespuesta.desde(await buscar.execute(criterios), idioma)


@router.get(
    "/servicios/{servicio_id}",
    summary="Detalle de un servicio (UC9)",
    response_model=ServicioDetalleRespuesta,
    responses={404: {"model": ErrorRespuesta}},
)
async def obtener_servicio(
    servicio_id: UUID,
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    obtener: Annotated[ObtenerServicio, Depends(get_obtener_servicio)],
) -> ServicioDetalleRespuesta:
    return ServicioDetalleRespuesta.desde(await obtener.execute(servicio_id), idioma)
