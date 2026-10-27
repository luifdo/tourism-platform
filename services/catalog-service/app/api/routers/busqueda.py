from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_buscar_servicios
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.routers.parametros import Pagina, categorias, coordenada_opcional, filtros_servicio
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.resultado_busqueda_respuesta import ResultadoBusquedaRespuesta
from app.application.dto.criterios_busqueda import (
    RADIO_MAXIMO_M,
    RADIO_POR_DEFECTO_M,
    CriteriosBusqueda,
    OrdenBusqueda,
)
from app.application.dto.filtros_servicio import FiltrosServicio
from app.application.use_cases.buscar_servicios import BuscarServicios
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog", tags=["Catálogo"])


@router.get(
    "/buscar",
    summary="Buscar y filtrar servicios (UC8)",
    response_model=ResultadoBusquedaRespuesta,
    responses={400: {"model": ErrorRespuesta}},
)
async def buscar_servicios(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    buscar: Annotated[BuscarServicios, Depends(get_buscar_servicios)],
    filtros: Annotated[FiltrosServicio, Depends(filtros_servicio)],
    texto: Annotated[str | None, Query(max_length=200)] = None,
    categoria: Annotated[str | None, Query(description="Una o varias, separadas por comas")] = None,
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
    precio_min: Annotated[Decimal | None, Query(ge=0)] = None,
    precio_max: Annotated[Decimal | None, Query(ge=0)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radio_m: Annotated[int, Query(ge=100, le=RADIO_MAXIMO_M)] = RADIO_POR_DEFECTO_M,
    orden: OrdenBusqueda = OrdenBusqueda.CALIFICACION,
    pagina: Pagina = 1,
    tamano: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ResultadoBusquedaRespuesta:
    criterios = CriteriosBusqueda(
        idioma=idioma,
        pagina=pagina,
        tamano=tamano,
        texto=texto,
        categorias=categorias(categoria),
        zona=zona,
        precio_min=precio_min,
        precio_max=precio_max,
        cerca_de=coordenada_opcional(lat, lon),
        radio_m=radio_m,
        orden=orden,
        filtros=filtros,
    )
    return ResultadoBusquedaRespuesta.desde(await buscar.execute(criterios), idioma)
