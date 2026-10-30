"""Repositorio de ElegibilidadResena (tabla `elegibilidad_resena`)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.elegibilidad_resena import ElegibilidadResena
from app.infrastructure.persistence.modelos.elegibilidad_resena import ElegibilidadResenaModelo


class SqlElegibilidadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, turista_id: UUID, servicio_id: UUID) -> ElegibilidadResena | None:
        m = ElegibilidadResenaModelo
        fila = await self._session.scalar(
            select(m).where(m.turista_id == turista_id, m.servicio_id == servicio_id)
        )
        if fila is None:
            return None
        return ElegibilidadResena(
            turista_id=fila.turista_id,
            servicio_id=fila.servicio_id,
            ultima_visita=fila.ultima_visita,
        )

    async def guardar(self, elegibilidad: ElegibilidadResena) -> None:
        # GREATEST en la base: si dos reserva.finalizada del mismo turista y servicio se
        # guardan a la vez (ninguno ve la fila del otro), queda la visita más reciente.
        m = ElegibilidadResenaModelo
        sentencia = insert(m).values(
            turista_id=elegibilidad.turista_id,
            servicio_id=elegibilidad.servicio_id,
            ultima_visita=elegibilidad.ultima_visita,
        )
        await self._session.execute(
            sentencia.on_conflict_do_update(
                index_elements=[m.turista_id, m.servicio_id],
                set_={
                    "ultima_visita": func.greatest(
                        m.ultima_visita, sentencia.excluded.ultima_visita
                    )
                },
            )
        )
