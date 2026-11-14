"""Repositorio de CalificacionResena (tabla `calificacion_resena`)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.calificacion_resena import CalificacionResena
from app.infrastructure.persistence.modelos.calificacion_resena import CalificacionResenaModelo
from app.infrastructure.persistence.repositorios.comun import upsert


class SqlCalificacionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, resena_id: UUID) -> CalificacionResena | None:
        fila = await self._session.scalar(
            select(CalificacionResenaModelo)
            .where(CalificacionResenaModelo.resena_id == resena_id)
            .with_for_update()
        )
        if fila is None:
            return None
        return CalificacionResena(
            resena_id=fila.resena_id,
            servicio_id=fila.servicio_id,
            puntuacion=fila.puntuacion,
            visible=fila.visible,
            ultimo_evento_en=fila.ultimo_evento_en,
        )

    async def guardar(self, calificacion: CalificacionResena) -> None:
        await upsert(
            self._session,
            CalificacionResenaModelo,
            {
                "resena_id": calificacion.resena_id,
                "servicio_id": calificacion.servicio_id,
                "puntuacion": calificacion.puntuacion,
                "visible": calificacion.visible,
                "ultimo_evento_en": calificacion.ultimo_evento_en,
                "actualizado_en": func.now(),
            },
            salvo_si_es_mas_nueva="ultimo_evento_en",
        )
