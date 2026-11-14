"""Analítica agregada sobre las proyecciones (implementa ConsultaAnalitica).

Todo por la fecha de la visita (`reserva_proyeccion.fecha_reserva`), con los índices
`ix_reserva_fecha_servicio` y `ix_reserva_prestador`. No hay caché: la consultan pocos
(prestadores y Entidad) y es rápida.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.agrupacion_demanda import AgrupacionDemanda
from app.application.dto.fila_metricas_servicio import FilaMetricasServicio
from app.application.dto.fila_reporte_demanda import FilaReporteDemanda
from app.application.dto.punto_demanda import PuntoDemanda
from app.application.dto.rango_fechas import RangoFechas
from app.application.dto.reservas_por_estado import ReservasPorEstado
from app.application.dto.zona_demandada import ZonaDemandada
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.value_objects.catalogos import Categoria
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio

_UNIDAD = {
    AgrupacionDemanda.DIA: "day",
    AgrupacionDemanda.SEMANA: "week",
    AgrupacionDemanda.MES: "month",
}

# Personas por estado actual; `canceladas` incluye las rechazadas.
_PERSONAS = """
    coalesce(sum(r.numero_personas) FILTER (WHERE r.estado = 'SOLICITADA'), 0)::int AS solicitadas,
    coalesce(sum(r.numero_personas) FILTER (WHERE r.estado = 'CONFIRMADA'), 0)::int AS confirmadas,
    coalesce(sum(r.numero_personas) FILTER (WHERE r.estado = 'FINALIZADA'), 0)::int AS finalizadas,
    coalesce(sum(r.numero_personas) FILTER (WHERE r.estado IN ('RECHAZADA', 'CANCELADA')), 0)::int
        AS canceladas
"""

_METRICAS_PRESTADOR = """
    SELECT s.id, s.nombre, s.capacidad_aforo_diario,
           count(r.reserva_id) FILTER (WHERE r.estado = 'SOLICITADA')::int AS n_solicitadas,
           count(r.reserva_id) FILTER (WHERE r.estado = 'CONFIRMADA')::int AS n_confirmadas,
           count(r.reserva_id) FILTER (WHERE r.estado = 'RECHAZADA')::int AS n_rechazadas,
           count(r.reserva_id) FILTER (WHERE r.estado = 'CANCELADA')::int AS n_canceladas,
           count(r.reserva_id) FILTER (WHERE r.estado = 'FINALIZADA')::int AS n_finalizadas,
           coalesce(sum(r.numero_personas) FILTER (WHERE r.estado = 'FINALIZADA'), 0)::int
               AS personas_finalizadas,
           c.promedio, coalesce(c.total, 0) AS total_resenas,
           coalesce(i.intenciones, 0) AS intenciones
    FROM atractivo_servicio s
    LEFT JOIN reserva_proyeccion r
        ON r.servicio_id = s.id AND r.fecha_reserva BETWEEN :desde AND :hasta
    LEFT JOIN LATERAL (
        SELECT avg(cr.puntuacion)::float AS promedio, count(*)::int AS total
        FROM calificacion_resena cr WHERE cr.servicio_id = s.id AND cr.visible
    ) c ON true
    LEFT JOIN LATERAL (
        SELECT sum(iv.conteo)::int AS intenciones FROM intencion_visita_dia iv
        WHERE iv.servicio_id = s.id AND iv.fecha BETWEEN :desde AND :hasta
    ) i ON true
    WHERE s.prestador_id = :prestador_id
    GROUP BY s.id, c.promedio, c.total, i.intenciones
    ORDER BY s.nombre ->> 'es', s.id
"""

_DEMANDA = f"""
    SELECT date_trunc(:unidad, r.fecha_reserva)::date AS periodo, {_PERSONAS}
    FROM reserva_proyeccion r
    JOIN atractivo_servicio s ON s.id = r.servicio_id
    LEFT JOIN zona z ON z.id = s.zona_id
    WHERE r.fecha_reserva BETWEEN :desde AND :hasta {{filtro}}
    GROUP BY 1
    ORDER BY 1
"""

_TOTALES = f"""
    SELECT {_PERSONAS}
    FROM reserva_proyeccion r
    WHERE r.fecha_reserva BETWEEN :desde AND :hasta
"""

_ZONAS_MAS_DEMANDADAS = """
    WITH personas AS (
        SELECT s.zona_id, sum(r.numero_personas)::int AS personas
        FROM reserva_proyeccion r
        JOIN atractivo_servicio s ON s.id = r.servicio_id
        WHERE r.fecha_reserva BETWEEN :desde AND :hasta
          AND r.estado IN ('SOLICITADA', 'CONFIRMADA', 'FINALIZADA')
        GROUP BY s.zona_id
    ), intenciones AS (
        SELECT s.zona_id, sum(iv.conteo)::int AS intenciones
        FROM intencion_visita_dia iv
        JOIN atractivo_servicio s ON s.id = iv.servicio_id
        WHERE iv.fecha BETWEEN :desde AND :hasta
        GROUP BY s.zona_id
    )
    SELECT z.codigo, z.nombre,
           coalesce(p.personas, 0) AS personas, coalesce(i.intenciones, 0) AS intenciones
    FROM zona z
    LEFT JOIN personas p ON p.zona_id = z.id
    LEFT JOIN intenciones i ON i.zona_id = z.id
    WHERE z.activa AND (coalesce(p.personas, 0) > 0 OR coalesce(i.intenciones, 0) > 0)
    ORDER BY personas DESC, intenciones DESC, z.codigo
    LIMIT :limite
"""


# Días con reservas o con intenciones de visita, por servicio.
_REPORTE_DEMANDA = f"""
    WITH reservas AS (
        SELECT r.servicio_id, r.fecha_reserva AS fecha, {_PERSONAS}
        FROM reserva_proyeccion r
        WHERE r.fecha_reserva BETWEEN :desde AND :hasta
        GROUP BY 1, 2
    ), intenciones AS (
        SELECT servicio_id, fecha, conteo
        FROM intencion_visita_dia
        WHERE fecha BETWEEN :desde AND :hasta
    ), dias AS (
        SELECT coalesce(r.servicio_id, i.servicio_id) AS servicio_id,
               coalesce(r.fecha, i.fecha) AS fecha,
               coalesce(r.solicitadas, 0) AS solicitadas,
               coalesce(r.confirmadas, 0) AS confirmadas,
               coalesce(r.finalizadas, 0) AS finalizadas,
               coalesce(r.canceladas, 0) AS canceladas,
               coalesce(i.conteo, 0) AS intenciones
        FROM reservas r
        FULL JOIN intenciones i ON i.servicio_id = r.servicio_id AND i.fecha = r.fecha
    )
    SELECT d.*, z.nombre ->> 'es' AS zona, s.nombre ->> 'es' AS servicio, s.categoria, s.tipo,
           s.capacidad_aforo_diario
    FROM dias d
    JOIN atractivo_servicio s ON s.id = d.servicio_id
    LEFT JOIN zona z ON z.id = s.zona_id
    WHERE true {{filtro}}
    ORDER BY d.fecha, z.nombre ->> 'es' NULLS LAST, s.nombre ->> 'es', s.id
"""


def _rango(rango: RangoFechas) -> dict[str, Any]:
    return {"desde": rango.desde, "hasta": rango.hasta}


def _punto(fila: Any, periodo: Any, zona: str | None = None) -> PuntoDemanda:
    return PuntoDemanda(
        periodo=periodo,
        solicitadas=fila.solicitadas,
        confirmadas=fila.confirmadas,
        finalizadas=fila.finalizadas,
        canceladas=fila.canceladas,
        zona=zona,
    )


class SqlConsultaAnalitica:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def metricas_prestador(
        self, prestador_id: UUID, rango: RangoFechas
    ) -> list[FilaMetricasServicio]:
        parametros = _rango(rango) | {"prestador_id": prestador_id}
        async with self._sesiones() as session:
            filas = (await session.execute(text(_METRICAS_PRESTADOR), parametros)).all()
        return [
            FilaMetricasServicio(
                servicio_id=f.id,
                nombre=TextoTraducido(**f.nombre),
                capacidad_aforo_diario=f.capacidad_aforo_diario,
                reservas=ReservasPorEstado(
                    solicitadas=f.n_solicitadas,
                    confirmadas=f.n_confirmadas,
                    rechazadas=f.n_rechazadas,
                    canceladas=f.n_canceladas,
                    finalizadas=f.n_finalizadas,
                ),
                personas_finalizadas=f.personas_finalizadas,
                calificacion_promedio=round(f.promedio, 2) if f.promedio is not None else None,
                total_resenas=f.total_resenas,
                intenciones_visita=f.intenciones,
            )
            for f in filas
        ]

    async def demanda(
        self,
        rango: RangoFechas,
        agrupacion: AgrupacionDemanda,
        zona: str | None,
        categoria: Categoria | None,
    ) -> list[PuntoDemanda]:
        parametros = _rango(rango) | {"unidad": _UNIDAD[agrupacion]}
        filtros = []
        if zona is not None:
            filtros.append("AND z.codigo = :zona")
            parametros["zona"] = zona
        if categoria is not None:
            filtros.append("AND s.categoria = :categoria")
            parametros["categoria"] = categoria.value
        sql = _DEMANDA.format(filtro=" ".join(filtros))
        async with self._sesiones() as session:
            filas = (await session.execute(text(sql), parametros)).all()
        return [_punto(f, f.periodo, zona) for f in filas]

    async def totales(self, rango: RangoFechas) -> PuntoDemanda:
        async with self._sesiones() as session:
            fila = (await session.execute(text(_TOTALES), _rango(rango))).one()
        return _punto(fila, rango.desde)

    async def zonas_mas_demandadas(self, rango: RangoFechas, limite: int) -> list[ZonaDemandada]:
        parametros = _rango(rango) | {"limite": limite}
        async with self._sesiones() as session:
            filas = (await session.execute(text(_ZONAS_MAS_DEMANDADAS), parametros)).all()
        return [
            ZonaDemandada(
                zona=ZonaResumen(f.codigo, TextoTraducido(**f.nombre)),
                personas=f.personas,
                intenciones_visita=f.intenciones,
            )
            for f in filas
        ]

    async def filas_reporte_demanda(
        self, rango: RangoFechas, zona: str | None
    ) -> AsyncIterator[FilaReporteDemanda]:
        parametros = _rango(rango)
        filtro = ""
        if zona is not None:
            filtro, parametros["zona"] = "AND z.codigo = :zona", zona
        sql = text(_REPORTE_DEMANDA.format(filtro=filtro))
        async with self._sesiones() as session:
            filas = await session.stream(sql, parametros)
            async for f in filas:
                yield FilaReporteDemanda(
                    fecha=f.fecha,
                    zona=f.zona,
                    servicio=f.servicio,
                    categoria=Categoria(f.categoria),
                    tipo=TipoServicio(f.tipo),
                    personas_solicitadas=f.solicitadas,
                    personas_confirmadas=f.confirmadas,
                    personas_finalizadas=f.finalizadas,
                    personas_canceladas=f.canceladas,
                    capacidad_recomendada=f.capacidad_aforo_diario,
                    intenciones_visita=f.intenciones,
                )
