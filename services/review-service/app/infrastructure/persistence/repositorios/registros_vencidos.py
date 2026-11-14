"""Borra la idempotencia vencida y los `evento_procesado` viejos (implementa RegistrosVencidos).

Son `DELETE` por condición: repetirlos, o correrlos en dos workers a la vez, no hace daño.
"""

from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.modelos.evento_procesado import EventoProcesadoModelo
from app.infrastructure.persistence.modelos.idempotencia import IdempotenciaModelo


class SqlRegistrosVencidos:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def borrar_idempotencia_vencida(self) -> int:
        m = IdempotenciaModelo
        async with self._sesiones.begin() as session:
            # now() de la base: el mismo reloj con el que se fijó `expira_en`.
            borradas = await session.scalars(
                delete(m).where(m.expira_en < text("now()")).returning(m.clave)
            )
            return len(borradas.all())

    async def borrar_eventos_procesados(self, antes_de: datetime) -> int:
        m = EventoProcesadoModelo
        async with self._sesiones.begin() as session:
            borrados = await session.scalars(
                delete(m).where(m.procesado_en < antes_de).returning(m.event_id)
            )
            return len(borrados.all())
