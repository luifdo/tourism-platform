"""Repositorio de ReservaProyeccion (tabla `reserva_proyeccion`)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.reserva_proyeccion import ReservaProyeccion
from app.domain.value_objects.catalogos import EstadoReserva
from app.infrastructure.persistence.modelos.reserva_proyeccion import ReservaProyeccionModelo
from app.infrastructure.persistence.repositorios.comun import upsert


class SqlReservaProyeccionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, reserva_id: UUID) -> ReservaProyeccion | None:
        fila = await self._session.scalar(
            select(ReservaProyeccionModelo)
            .where(ReservaProyeccionModelo.reserva_id == reserva_id)
            .with_for_update()
        )
        if fila is None:
            return None
        return ReservaProyeccion(
            reserva_id=fila.reserva_id,
            servicio_id=fila.servicio_id,
            prestador_id=fila.prestador_id,
            turista_id=fila.turista_id,
            fecha_reserva=fila.fecha_reserva,
            numero_personas=fila.numero_personas,
            estado=EstadoReserva(fila.estado),
            ultimo_evento_en=fila.ultimo_evento_en,
        )

    async def guardar(self, reserva: ReservaProyeccion) -> None:
        await upsert(
            self._session,
            ReservaProyeccionModelo,
            {
                "reserva_id": reserva.reserva_id,
                "servicio_id": reserva.servicio_id,
                "prestador_id": reserva.prestador_id,
                "turista_id": reserva.turista_id,
                "fecha_reserva": reserva.fecha_reserva,
                "numero_personas": reserva.numero_personas,
                "estado": reserva.estado.value,
                "ultimo_evento_en": reserva.ultimo_evento_en,
            },
            salvo_si_es_mas_nueva="ultimo_evento_en",
        )
