"""Capas GeoJSON para el mapa de OpenStreetMap en Leaflet (UC16)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_ver_alertas_en_mapa,
    get_ver_servicios_en_mapa,
    get_ver_zonas_en_mapa,
)
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.respuesta_geojson import RespuestaGeoJSON
from app.api.routers.parametros import bbox, bbox_opcional, categorias, filtros_servicio
from app.api.schemas.coleccion_alertas_mapa import ColeccionAlertasMapa
from app.api.schemas.coleccion_servicios_mapa import ColeccionServiciosMapa
from app.api.schemas.coleccion_zonas_mapa import ColeccionZonasMapa
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.application.dto.criterios_mapa_servicios import CriteriosMapaServicios
from app.application.dto.escala_mapa import ZOOM_MAXIMO, ZOOM_MINIMO, EscalaMapa
from app.application.dto.filtros_servicio import FiltrosServicio
from app.application.use_cases.ver_alertas_en_mapa import VerAlertasEnMapa
from app.application.use_cases.ver_servicios_en_mapa import VerServiciosEnMapa
from app.application.use_cases.ver_zonas_en_mapa import VerZonasEnMapa
from app.domain.value_objects.idioma import Idioma

router = APIRouter(
    prefix="/api/catalog/mapa", tags=["Mapa"], default_response_class=RespuestaGeoJSON
)

_BBOX = "Vista del mapa como minLon,minLat,maxLon,maxLat"
Zoom = Annotated[int, Query(ge=ZOOM_MINIMO, le=ZOOM_MAXIMO, description="Zoom de Leaflet")]


@router.get(
    "/servicios",
    summary="Servicios en la vista del mapa (UC16)",
    response_model=ColeccionServiciosMapa,
    responses={400: {"model": ErrorRespuesta}},
)
async def servicios_en_mapa(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    ver: Annotated[VerServiciosEnMapa, Depends(get_ver_servicios_en_mapa)],
    vista: Annotated[str, Query(alias="bbox", description=_BBOX)],
    zoom: Zoom,
    filtros: Annotated[FiltrosServicio, Depends(filtros_servicio)],
    categoria: Annotated[str | None, Query(description="Una o varias, separadas por comas")] = None,
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
) -> ColeccionServiciosMapa:
    criterios = CriteriosMapaServicios(
        vista=bbox(vista),
        escala=EscalaMapa(zoom),
        categorias=categorias(categoria),
        zona=zona,
        filtros=filtros,
    )
    return ColeccionServiciosMapa.desde(await ver.execute(criterios), idioma)


@router.get(
    "/zonas",
    summary="Polígonos de las zonas (UC16)",
    response_model=ColeccionZonasMapa,
    responses={400: {"model": ErrorRespuesta}},
)
async def zonas_en_mapa(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    ver: Annotated[VerZonasEnMapa, Depends(get_ver_zonas_en_mapa)],
    zoom: Zoom,
    vista: Annotated[str | None, Query(alias="bbox", description=_BBOX)] = None,
) -> ColeccionZonasMapa:
    zonas = await ver.execute(bbox_opcional(vista), EscalaMapa(zoom))
    return ColeccionZonasMapa.desde(zonas, idioma)


@router.get(
    "/alertas",
    summary="Alertas vigentes en la vista del mapa (UC16, UC26)",
    response_model=ColeccionAlertasMapa,
    responses={400: {"model": ErrorRespuesta}},
)
async def alertas_en_mapa(
    idioma: Annotated[Idioma, Depends(idioma_peticion)],
    ver: Annotated[VerAlertasEnMapa, Depends(get_ver_alertas_en_mapa)],
    vista: Annotated[str | None, Query(alias="bbox", description=_BBOX)] = None,
) -> ColeccionAlertasMapa:
    return ColeccionAlertasMapa.desde(await ver.execute(bbox_opcional(vista)), idioma)
