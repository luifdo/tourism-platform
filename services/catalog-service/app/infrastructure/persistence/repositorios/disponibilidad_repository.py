"""Repositorio de DisponibilidadDia (tabla `disponibilidad_proyeccion`)."""

from datetime import date
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.disponibilidad_dia import DisponibilidadDia
from app.infrastructure.persistence.modelos.disponibilidad_proyeccion import (
    DisponibilidadProyeccionModelo,
)
from app.infrastructure.persistence.repositorios.comun import upsert


class SqlDisponibilidadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, servicio_id: UUID, fecha: date) -> DisponibilidadDia | None:
        m = DisponibilidadProyeccionModelo
        fila = await self._session.scalar(
            select(m).where(m.servicio_id == servicio_id, m.fecha == fecha).with_for_update()
        )
        if fila is None:
            return None
        return DisponibilidadDia(
            servicio_id=fila.servicio_id,
            fecha=fila.fecha,
            cupos_totales=fila.cupos_totales,
            cupos_disponibles=fila.cupos_disponibles,
            version=fila.version,
        )

    async def guardar(self, dia: DisponibilidadDia) -> None:
        await upsert(
            self._session,
            DisponibilidadProyeccionModelo,
            {
                "servicio_id": dia.servicio_id,
                "fecha": dia.fecha,
                "cupos_totales": dia.cupos_totales,
                "cupos_disponibles": dia.cupos_disponibles,
                "version": dia.version,
                "actualizado_en": func.now(),
            },
            salvo_si_es_mas_nueva="version",
        )

    async def borrar_anteriores(self, fecha: date) -> int:
        m = DisponibilidadProyeccionModelo
        resultado = await self._session.execute(delete(m).where(m.fecha < fecha))
        return resultado.rowcount or 0
