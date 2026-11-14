"""Lectura de zonas (implementa ConsultaZonas), sin bloquear filas."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.zona_vista import ZonaVista
from app.domain.entities.zona import Zona
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.modelos.zona import ZonaModelo
from app.infrastructure.persistence.repositorios.zona_repository import (
    columnas_zona,
    zona_desde_fila,
)

# ST_PointOnSurface garantiza un punto dentro del polígono (el centroide puede caer fuera).
# Se redondea a 6 decimales (~10 cm) para no exponer ruido de punto flotante.
_ACTIVAS = """
    SELECT id, codigo, nombre,
           round(ST_Y(ST_PointOnSurface(poligono))::numeric, 6)::float8 AS lat,
           round(ST_X(ST_PointOnSurface(poligono))::numeric, 6)::float8 AS lon
    FROM zona
    WHERE activa
    ORDER BY codigo
"""


class SqlConsultaZonas:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def activas(self) -> list[ZonaVista]:
        async with self._sesiones() as session:
            filas = (await session.execute(text(_ACTIVAS))).all()
        return [
            ZonaVista(
                id=f.id,
                codigo=f.codigo,
                nombre=TextoTraducido(**f.nombre),
                centro=Coordenada(lat=f.lat, lon=f.lon),
            )
            for f in filas
        ]

    async def zona(self, zona_id: UUID) -> Zona | None:
        async with self._sesiones() as session:
            fila = (
                await session.execute(select(*columnas_zona()).where(ZonaModelo.id == zona_id))
            ).first()
        return zona_desde_fila(*fila) if fila else None
