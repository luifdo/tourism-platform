"""Lectura del mapa con PostGIS (implementa ConsultaMapa).

* La vista se recorta con `&&` / ST_Intersects contra ST_MakeEnvelope en `geometry`, que es
  exacto en grados y usa los índices GIST (`ix_servicio_ubicacion_plana`, `ix_zona_poligono`).
* Con zoom bajo los puntos se agrupan en el servidor por celdas de `floor(lon / celda)`: al
  móvil llegan decenas de grupos en vez de miles de marcadores.
* Los polígonos se simplifican con ST_SimplifyPreserveTopology (no se cruzan ni desaparecen)
  y salen siempre como MultiPolygon (simplificar puede devolver un Polygon), en GeoJSON con
  6 decimales (~10 cm) y en `[lon, lat]`.
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.alerta_en_mapa import AlertaEnMapa
from app.application.dto.criterios_mapa_servicios import (
    MAXIMO_INDIVIDUALES,
    CriteriosMapaServicios,
)
from app.application.dto.escala_mapa import EscalaMapa
from app.application.dto.grupo_en_mapa import GrupoEnMapa
from app.application.dto.mapa_servicios import MapaServicios
from app.application.dto.servicio_en_mapa import ServicioEnMapa
from app.application.dto.zona_en_mapa import ZonaEnMapa
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.geo import Bbox, Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.consultas.condiciones_filtros import agregar_filtros
from app.infrastructure.persistence.consultas.sql_consulta_alertas import (
    ORDEN_POR_NIVEL,
    alerta_desde_fila,
)

_VISTA = "ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)"
_PROMEDIO = """
    LEFT JOIN LATERAL (
        SELECT avg(r.puntuacion)::float AS promedio
        FROM calificacion_resena r WHERE r.servicio_id = {id} AND r.visible
    ) c ON true
"""

# El promedio de calificación solo se calcula para los grupos de un servicio.
_AGRUPADOS = f"""
    WITH grupos AS (
        SELECT count(*) AS conteo, avg(s.lat) AS lat, avg(s.lon) AS lon,
               (array_agg(s.id))[1] AS id, (array_agg(s.nombre))[1] AS nombre,
               (array_agg(s.categoria))[1] AS categoria
        FROM atractivo_servicio s {{union_zona}}
        WHERE {{condiciones}}
        GROUP BY floor(s.lon / :celda), floor(s.lat / :celda)
    )
    SELECT g.*, c.promedio FROM grupos g
    {_PROMEDIO.format(id="CASE WHEN g.conteo = 1 THEN g.id END")}
"""

# Si una vista con zoom alto trae demasiados, se muestran los mejor calificados.
_INDIVIDUALES = f"""
    SELECT 1 AS conteo, s.lat, s.lon, s.id, s.nombre, s.categoria, c.promedio
    FROM atractivo_servicio s {{union_zona}}
    {_PROMEDIO.format(id="s.id")}
    WHERE {{condiciones}}
    ORDER BY c.promedio DESC NULLS LAST, s.id
    LIMIT :limite
"""

_ZONAS = """
    SELECT id, codigo, nombre,
           ST_AsGeoJSON(ST_Multi(ST_SimplifyPreserveTopology(poligono, :tolerancia)), 6)
               AS geometria
    FROM zona
    WHERE activa {filtro}
    ORDER BY codigo
"""

# Una alerta de servicio se dibuja en su punto; una de zona, en su polígono.
_GEOMETRIA_ALERTA = "coalesce(s.ubicacion::geometry, z.poligono)"
_ALERTAS = f"""
    SELECT a.id, a.nivel, a.mensaje, a.servicio_id, a.fecha_expiracion,
           z.codigo AS zona_codigo, z.nombre AS zona_nombre,
           ST_AsGeoJSON({_GEOMETRIA_ALERTA}, 6) AS geometria
    FROM alerta_oficial a
    LEFT JOIN zona z ON z.id = a.zona_id AND z.activa
    LEFT JOIN atractivo_servicio s ON s.id = a.servicio_id AND s.activo
    WHERE a.activa AND a.fecha_expiracion > :ahora
      AND {_GEOMETRIA_ALERTA} IS NOT NULL {{filtro}}
"""


def _parametros_vista(vista: Bbox) -> dict[str, float]:
    return {
        "min_lon": vista.min_lon,
        "min_lat": vista.min_lat,
        "max_lon": vista.max_lon,
        "max_lat": vista.max_lat,
    }


def _coordenada(fila: Any) -> Coordenada:
    return Coordenada(lat=round(fila.lat, 6), lon=round(fila.lon, 6))


class SqlConsultaMapa:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def servicios(self, criterios: CriteriosMapaServicios) -> MapaServicios:
        condiciones = ["s.activo", f"s.ubicacion::geometry && {_VISTA}"]
        parametros: dict[str, Any] = _parametros_vista(criterios.vista)
        union_zona = ""
        if criterios.categorias:
            condiciones.append("s.categoria = ANY(:categorias)")
            parametros["categorias"] = [c.value for c in criterios.categorias]
        agregar_filtros(criterios.filtros, condiciones, parametros)
        if criterios.zona:
            union_zona = "JOIN zona z ON z.id = s.zona_id AND z.activa AND z.codigo = :zona"
            parametros["zona"] = criterios.zona

        if criterios.escala.agrupa:
            plantilla = _AGRUPADOS
            parametros["celda"] = criterios.escala.celda_grados
        else:
            plantilla = _INDIVIDUALES
            parametros["limite"] = MAXIMO_INDIVIDUALES
        sql = plantilla.format(union_zona=union_zona, condiciones=" AND ".join(condiciones))
        async with self._sesiones() as session:
            filas = (await session.execute(text(sql), parametros)).all()

        servicios = tuple(
            ServicioEnMapa(
                id=f.id,
                nombre=TextoTraducido(**f.nombre),
                categoria=Categoria(f.categoria),
                ubicacion=_coordenada(f),
                calificacion_promedio=round(f.promedio, 2) if f.promedio is not None else None,
            )
            for f in filas
            if f.conteo == 1
        )
        grupos = tuple(
            GrupoEnMapa(ubicacion=_coordenada(f), conteo=f.conteo) for f in filas if f.conteo > 1
        )
        return MapaServicios(servicios=servicios, grupos=grupos)

    async def zonas(self, vista: Bbox | None, escala: EscalaMapa) -> list[ZonaEnMapa]:
        parametros: dict[str, Any] = {"tolerancia": escala.tolerancia_grados}
        filtro = ""
        if vista is not None:
            filtro = f"AND ST_Intersects(poligono, {_VISTA})"
            parametros |= _parametros_vista(vista)
        async with self._sesiones() as session:
            filas = (await session.execute(text(_ZONAS.format(filtro=filtro)), parametros)).all()
        return [
            ZonaEnMapa(
                id=f.id,
                codigo=f.codigo,
                nombre=TextoTraducido(**f.nombre),
                geometria=json.loads(f.geometria),
            )
            for f in filas
        ]

    async def alertas(self, ahora: datetime, vista: Bbox | None) -> list[AlertaEnMapa]:
        parametros: dict[str, Any] = {"ahora": ahora}
        filtro = ""
        if vista is not None:
            filtro = f"AND ST_Intersects({_GEOMETRIA_ALERTA}, {_VISTA})"
            parametros |= _parametros_vista(vista)
        sql = _ALERTAS.format(filtro=filtro) + ORDEN_POR_NIVEL
        async with self._sesiones() as session:
            filas = (await session.execute(text(sql), parametros)).all()
        return [
            AlertaEnMapa(alerta=alerta_desde_fila(f), geometria=json.loads(f.geometria))
            for f in filas
        ]
