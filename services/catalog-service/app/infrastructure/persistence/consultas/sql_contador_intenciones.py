"""Conteo de intenciones de visita en `intencion_visita_dia` (implementa ContadorIntenciones)."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.intenciones_zona_dia import IntencionesZonaDia
from app.application.dto.rango_fechas import RangoFechas

# Una sola sentencia: solo suma si el servicio existe y está activo.
_SUMAR = """
    INSERT INTO intencion_visita_dia (servicio_id, fecha, conteo)
    SELECT s.id, :fecha, 1 FROM atractivo_servicio s WHERE s.id = :servicio_id AND s.activo
    ON CONFLICT (servicio_id, fecha)
        DO UPDATE SET conteo = intencion_visita_dia.conteo + 1
    RETURNING conteo
"""

# Por la zona en la que está hoy cada servicio.
_POR_ZONA = """
    SELECT z.codigo AS zona, i.fecha, sum(i.conteo)::int AS intenciones
    FROM intencion_visita_dia i
    JOIN atractivo_servicio s ON s.id = i.servicio_id
    JOIN zona z ON z.id = s.zona_id
    WHERE i.fecha BETWEEN :desde AND :hasta {filtro}
    GROUP BY z.codigo, i.fecha
    ORDER BY i.fecha, z.codigo
"""


class SqlContadorIntenciones:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def sumar(self, servicio_id: UUID, fecha: date) -> bool:
        async with self._sesiones() as session, session.begin():
            fila = (
                await session.execute(text(_SUMAR), {"servicio_id": servicio_id, "fecha": fecha})
            ).first()
        return fila is not None

    async def por_zona(self, rango: RangoFechas, zona: str | None) -> list[IntencionesZonaDia]:
        parametros: dict[str, Any] = {"desde": rango.desde, "hasta": rango.hasta}
        filtro = ""
        if zona is not None:
            filtro, parametros["zona"] = "AND z.codigo = :zona", zona
        async with self._sesiones() as session:
            filas = (await session.execute(text(_POR_ZONA.format(filtro=filtro)), parametros)).all()
        return [IntencionesZonaDia(f.zona, f.fecha, f.intenciones) for f in filas]
