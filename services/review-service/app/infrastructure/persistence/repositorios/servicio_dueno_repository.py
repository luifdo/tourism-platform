"""Repositorio de ServicioDueno (tabla `servicio_dueno`)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.servicio_dueno import ServicioDueno
from app.infrastructure.persistence.modelos.servicio_dueno import ServicioDuenoModelo


class SqlServicioDuenoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, servicio_id: UUID) -> ServicioDueno | None:
        fila = await self._session.scalar(
            select(ServicioDuenoModelo).where(ServicioDuenoModelo.servicio_id == servicio_id)
        )
        if fila is None:
            return None
        return ServicioDueno(
            servicio_id=fila.servicio_id,
            prestador_usuario_id=fila.prestador_usuario_id,
            version=fila.version,
        )

    async def guardar(self, servicio: ServicioDueno) -> None:
        # La misma regla que la entidad, pero atómica: con dos servicio.publicado del mismo
        # servicio a la vez, la base deja la versión mayor sin importar cuál confirma primero.
        m = ServicioDuenoModelo
        sentencia = insert(m).values(
            servicio_id=servicio.servicio_id,
            prestador_usuario_id=servicio.prestador_usuario_id,
            version=servicio.version,
        )
        await self._session.execute(
            sentencia.on_conflict_do_update(
                index_elements=[m.servicio_id],
                set_={
                    "prestador_usuario_id": sentencia.excluded.prestador_usuario_id,
                    "version": sentencia.excluded.version,
                },
                where=m.version < sentencia.excluded.version,
            )
        )
