"""Analítica del destino: demanda (UC23), capacidad de carga (UC24), tablero (UC25), mapa de
calor (RF-07) y reporte CSV (UC38). Todo por la fecha de la visita."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.dependencies import (
    get_consultar_capacidad,
    get_consultar_demanda,
    get_exportar_reporte_demanda,
    get_ver_mapa_calor,
    get_ver_tablero,
)
from app.api.i18n.idioma_peticion import idioma_peticion
from app.api.reportes.csv_reporte_demanda import generar_csv, nombre_archivo
from app.api.respuesta_geojson import RespuestaGeoJSON
from app.api.routers.parametros import Fecha, bbox_opcional
from app.api.schemas.capacidad_zona_respuesta import CapacidadZonaRespuesta
from app.api.schemas.coleccion_mapa_calor import ColeccionMapaCalor
from app.api.schemas.error_respuesta import ErrorRespuesta
from app.api.schemas.serie_demanda_respuesta import SerieDemandaRespuesta
from app.api.schemas.tablero_respuesta import TableroRespuesta
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.escala_mapa import ZOOM_MAXIMO, ZOOM_MINIMO, EscalaMapa
from app.application.dto.rango_fechas import RangoFechas
from app.application.use_cases.consultar_capacidad import ConsultarCapacidad
from app.application.use_cases.consultar_demanda import ConsultarDemanda
from app.application.use_cases.exportar_reporte_demanda import ExportarReporteDemanda
from app.application.use_cases.ver_mapa_calor import VerMapaCalor
from app.application.use_cases.ver_tablero import VerTablero
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.idioma import Idioma

router = APIRouter(prefix="/api/catalog/analitica", tags=["Analítica"])

IdentidadDep = Annotated[Identidad, Depends(identidad_peticion)]
IdiomaDep = Annotated[Idioma, Depends(idioma_peticion)]
_ERRORES = {
    400: {"model": ErrorRespuesta},
    401: {"model": ErrorRespuesta},
    403: {"model": ErrorRespuesta},
}


@router.get(
    "/capacidad",
    summary="Presión sobre la capacidad de carga (UC24)",
    response_model=list[CapacidadZonaRespuesta],
    responses=_ERRORES | {404: {"model": ErrorRespuesta}},
)
async def capacidad(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    consultar: Annotated[ConsultarCapacidad, Depends(get_consultar_capacidad)],
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
    fecha: Fecha | None = None,
) -> JSONResponse:
    zonas = await consultar.execute(identidad, fecha, zona)
    solo_nivel = identidad.rol is Rol.TURISTA
    cuerpo = [
        CapacidadZonaRespuesta.desde(z, idioma, solo_nivel).model_dump(
            mode="json", exclude_none=True
        )
        for z in zonas
    ]
    return JSONResponse(cuerpo, headers={"Content-Language": idioma.value})


@router.get(
    "/mapa-calor",
    summary="Mapa de calor de saturación por zona (RF-07)",
    response_model=ColeccionMapaCalor,
    response_class=RespuestaGeoJSON,
    responses=_ERRORES,
)
async def mapa_calor(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    ver: Annotated[VerMapaCalor, Depends(get_ver_mapa_calor)],
    fecha: Fecha | None = None,
    vista: Annotated[str | None, Query(alias="bbox")] = None,
    zoom: Annotated[int, Query(ge=ZOOM_MINIMO, le=ZOOM_MAXIMO)] = 12,
) -> ColeccionMapaCalor:
    zonas = await ver.execute(identidad, fecha, bbox_opcional(vista), EscalaMapa(zoom))
    return ColeccionMapaCalor.desde(zonas, idioma)


@router.get(
    "/demanda",
    summary="Indicadores agregados de demanda (UC23)",
    response_model=SerieDemandaRespuesta,
    responses=_ERRORES | {404: {"model": ErrorRespuesta}},
)
async def demanda(
    identidad: IdentidadDep,
    consultar: Annotated[ConsultarDemanda, Depends(get_consultar_demanda)],
    desde: Fecha,
    hasta: Fecha,
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
    categoria: Categoria | None = None,
    agrupacion: AgrupacionDemanda = AgrupacionDemanda.DIA,
) -> SerieDemandaRespuesta:
    serie = await consultar.execute(
        identidad, RangoFechas(desde, hasta), agrupacion, zona, categoria
    )
    return SerieDemandaRespuesta.desde(serie)


@router.get(
    "/tablero",
    summary="Tablero de planificación (UC25)",
    response_model=TableroRespuesta,
    responses=_ERRORES,
)
async def tablero(
    identidad: IdentidadDep,
    idioma: IdiomaDep,
    ver: Annotated[VerTablero, Depends(get_ver_tablero)],
    desde: Fecha,
    hasta: Fecha,
) -> TableroRespuesta:
    return TableroRespuesta.desde_dto(
        await ver.execute(identidad, RangoFechas(desde, hasta)), idioma
    )


@router.get(
    "/reportes/demanda",
    summary="Exportar el reporte de demanda (UC38)",
    response_class=StreamingResponse,
    responses=_ERRORES | {200: {"content": {"text/csv": {}}}, 404: {"model": ErrorRespuesta}},
)
async def reporte_demanda(
    identidad: IdentidadDep,
    exportar: Annotated[ExportarReporteDemanda, Depends(get_exportar_reporte_demanda)],
    desde: Fecha,
    hasta: Fecha,
    zona: Annotated[str | None, Query(pattern=r"^[a-z0-9-]{2,40}$")] = None,
    formato: Annotated[str, Query(pattern="^csv$")] = "csv",
) -> StreamingResponse:
    filas = await exportar.execute(identidad, RangoFechas(desde, hasta), zona)
    archivo = nombre_archivo(desde.isoformat(), hasta.isoformat())
    return StreamingResponse(
        generar_csv(filas),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{archivo}"'},
    )
