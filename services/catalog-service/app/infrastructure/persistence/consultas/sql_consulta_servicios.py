"""Lectura del catálogo con PostGIS (implementa ConsultaServicios).

* Distancia con `geography`: ST_DWithin y ST_Distance trabajan en metros y usan el índice GIST.
* Texto con la columna `tsvector` del idioma pedido y `websearch_to_tsquery` (admite frases
  entre comillas y `-palabra`), sin tildes.
* Los filtros de tipo y atributos los arma `agregar_filtros`, igual que en el mapa.
* Las condiciones se agregan solo si el filtro viene: así PostgreSQL elige el mejor índice y
  asyncpg no tiene que adivinar el tipo de parámetros nulos.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.criterios_busqueda import CriteriosBusqueda, OrdenBusqueda
from app.application.dto.pagina_servicios import PaginaServicios
from app.application.dto.prestador_publico import PrestadorPublico
from app.application.dto.servicio_detalle import ServicioDetalle
from app.application.dto.servicio_resumen import ServicioResumen
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.catalogos import Categoria, UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.consultas.condiciones_filtros import (
    COLUMNA_CUPOS,
    agregar_filtros,
)
from app.infrastructure.persistence.consultas.sql_consulta_alertas import SqlConsultaAlertas
from app.infrastructure.persistence.repositorios.comun import texto_o_none

_TEXTO_POR_IDIOMA = {Idioma.ES: ("busqueda_es", "spanish"), Idioma.EN: ("busqueda_en", "english")}

_COLUMNAS = """
    s.id, s.nombre, s.tipo, s.categoria, s.lat, s.lon, s.tarifa_base, s.unidad_tarifa,
    s.imagenes_urls[1] AS imagen,
    z.codigo AS zona_codigo, z.nombre AS zona_nombre,
    c.promedio, coalesce(c.total, 0) AS total_resenas
"""
_ORIGEN = """
    FROM atractivo_servicio s
    LEFT JOIN zona z ON z.id = s.zona_id AND z.activa
    LEFT JOIN LATERAL (
        SELECT avg(r.puntuacion)::float AS promedio, count(*) AS total
        FROM calificacion_resena r WHERE r.servicio_id = s.id AND r.visible
    ) c ON true
"""
_PUNTO = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography"


def _resumen(fila: Any, distancia: float | None = None, con_fecha: bool = False) -> ServicioResumen:
    zona = (
        ZonaResumen(codigo=fila.zona_codigo, nombre=TextoTraducido(**fila.zona_nombre))
        if fila.zona_codigo
        else None
    )
    return ServicioResumen(
        id=fila.id,
        nombre=TextoTraducido(**fila.nombre),
        tipo=TipoServicio(fila.tipo),
        categoria=Categoria(fila.categoria),
        ubicacion=Coordenada(lat=fila.lat, lon=fila.lon),
        tarifa_base=Decimal(fila.tarifa_base),
        unidad_tarifa=UnidadTarifa(fila.unidad_tarifa),
        zona=zona,
        calificacion_promedio=round(fila.promedio, 2) if fila.promedio is not None else None,
        total_resenas=fila.total_resenas,
        imagen_principal=fila.imagen,
        distancia_m=round(distancia) if distancia is not None else None,
        cupos_disponibles=fila.cupos if con_fecha else None,
        disponibilidad_confirmada=(fila.cupos is not None) if con_fecha else None,
    )


class SqlConsultaServicios:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones
        self._alertas = SqlConsultaAlertas(sesiones)

    async def buscar(self, criterios: CriteriosBusqueda) -> PaginaServicios:
        columnas = [_COLUMNAS]
        condiciones = ["s.activo"]
        parametros: dict[str, Any] = {
            "limite": criterios.tamano,
            "desplazamiento": (criterios.pagina - 1) * criterios.tamano,
        }

        if criterios.categorias:
            condiciones.append("s.categoria = ANY(:categorias)")
            parametros["categorias"] = [c.value for c in criterios.categorias]
        agregar_filtros(criterios.filtros, condiciones, parametros)
        con_fecha = criterios.filtros.fecha is not None
        if con_fecha:
            columnas.append(COLUMNA_CUPOS)
        if criterios.zona:
            condiciones.append("z.codigo = :zona")
            parametros["zona"] = criterios.zona
        if criterios.precio_min is not None:
            condiciones.append("s.tarifa_base >= :precio_min")
            parametros["precio_min"] = criterios.precio_min
        if criterios.precio_max is not None:
            condiciones.append("s.tarifa_base <= :precio_max")
            parametros["precio_max"] = criterios.precio_max
        if criterios.cerca_de:
            columnas.append(f"ST_Distance(s.ubicacion, {_PUNTO}) AS distancia")
            condiciones.append(f"ST_DWithin(s.ubicacion, {_PUNTO}, :radio)")
            parametros |= {
                "lat": criterios.cerca_de.lat,
                "lon": criterios.cerca_de.lon,
                "radio": criterios.radio_m,
            }
        if criterios.texto:
            columna, configuracion = _TEXTO_POR_IDIOMA[criterios.idioma]
            consulta_texto = f"websearch_to_tsquery('{configuracion}', f_unaccent(:texto))"
            columnas.append(f"ts_rank(s.{columna}, {consulta_texto}) AS relevancia")
            condiciones.append(f"s.{columna} @@ {consulta_texto}")
            parametros["texto"] = criterios.texto

        orden = {
            OrdenBusqueda.RELEVANCIA: "relevancia DESC",
            OrdenBusqueda.DISTANCIA: "distancia ASC",
            OrdenBusqueda.PRECIO: "s.tarifa_base ASC",
            OrdenBusqueda.CALIFICACION: "c.promedio DESC NULLS LAST, total_resenas DESC",
        }[criterios.orden]

        sql = f"""
            SELECT {", ".join(columnas)}, count(*) OVER () AS total_filas
            {_ORIGEN}
            WHERE {" AND ".join(condiciones)}
            ORDER BY {orden}, s.id
            LIMIT :limite OFFSET :desplazamiento
        """
        async with self._sesiones() as session:
            filas = (await session.execute(text(sql), parametros)).all()
            if filas:
                total = filas[0].total_filas
            else:
                # Página fuera de rango: el total se cuenta aparte.
                total = await session.scalar(
                    text(f"SELECT count(*) {_ORIGEN} WHERE {' AND '.join(condiciones)}"),
                    parametros,
                )

        items = tuple(
            _resumen(f, f.distancia if criterios.cerca_de else None, con_fecha) for f in filas
        )
        return PaginaServicios(
            items=items, pagina=criterios.pagina, tamano=criterios.tamano, total=total or 0
        )

    async def detalle(self, servicio_id: UUID, ahora: datetime) -> ServicioDetalle | None:
        sql = f"""
            SELECT {_COLUMNAS}, s.descripcion, s.capacidad_aforo_diario, s.imagenes_urls,
                   s.atributos,
                   p.id AS prestador_id, p.razon_social, p.telefono, p.politica_cancelacion
            {_ORIGEN}
            JOIN prestador_perfil p ON p.id = s.prestador_id
            WHERE s.id = :id AND s.activo
        """
        async with self._sesiones() as session:
            fila = (await session.execute(text(sql), {"id": servicio_id})).first()
        if fila is None:
            return None
        alertas = await self._alertas.vigentes(ahora, servicio_id=servicio_id)
        return ServicioDetalle(
            resumen=_resumen(fila),
            descripcion=TextoTraducido(**fila.descripcion),
            capacidad_aforo_diario=fila.capacidad_aforo_diario,
            imagenes_urls=tuple(fila.imagenes_urls),
            prestador=PrestadorPublico(
                id=fila.prestador_id,
                razon_social=fila.razon_social,
                telefono=fila.telefono,
                politica_cancelacion=texto_o_none(fila.politica_cancelacion),
            ),
            alertas=tuple(alertas),
            atributos=AtributosServicio.desde_json(fila.atributos),
        )
