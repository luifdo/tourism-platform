"""Repositorio de Resena (tabla `resena`).

Aspectos y respuesta van en JSONB: `{"LIMPIEZA": 5}` y `{"texto": ..., "respondida_en": ...}`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.resena import Resena
from app.domain.errors import YaResenado
from app.domain.value_objects.aspecto import Aspecto
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.respuesta_prestador import RespuestaPrestador
from app.infrastructure.persistence.modelos.resena import ResenaModelo
from app.infrastructure.persistence.repositorios.comun import upsert, viola

UNA_POR_TURISTA = "uq_resena_turista_servicio"


def respuesta_desde_json(valor: dict[str, Any] | None) -> RespuestaPrestador | None:
    if valor is None:
        return None
    return RespuestaPrestador(
        texto=valor["texto"], respondida_en=datetime.fromisoformat(valor["respondida_en"])
    )


def resena_desde_modelo(fila: ResenaModelo) -> Resena:
    """También la usan las consultas de lectura, que leen sin bloquear filas."""
    return Resena(
        id=fila.id,
        servicio_id=fila.servicio_id,
        turista_id=fila.turista_id,
        contenido=ContenidoResena(
            fila.puntuacion,
            {Aspecto(a): v for a, v in fila.aspectos.items()},
            fila.comentario,
        ),
        ultima_visita=fila.ultima_visita,
        creada_en=fila.creada_en,
        estado=EstadoResena(fila.estado),
        respuesta=respuesta_desde_json(fila.respuesta),
        reportes_pendientes=fila.reportes_pendientes,
        editada_en=fila.editada_en,
        version=fila.version,
    )


class SqlResenaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, resena_id: UUID) -> Resena | None:
        fila = await self._session.scalar(
            select(ResenaModelo).where(ResenaModelo.id == resena_id).with_for_update()
        )
        return resena_desde_modelo(fila) if fila else None

    async def obtener_de_turista(self, turista_id: UUID, servicio_id: UUID) -> Resena | None:
        fila = await self._session.scalar(
            select(ResenaModelo).where(
                ResenaModelo.turista_id == turista_id, ResenaModelo.servicio_id == servicio_id
            )
        )
        return resena_desde_modelo(fila) if fila else None

    async def guardar(self, resena: Resena) -> None:
        r = resena.respuesta
        valores = {
            "id": resena.id,
            "servicio_id": resena.servicio_id,
            "turista_id": resena.turista_id,
            "puntuacion": resena.contenido.puntuacion,
            "aspectos": {a.value: v for a, v in resena.contenido.aspectos.items()},
            "comentario": resena.contenido.comentario,
            "respuesta": (
                {"texto": r.texto, "respondida_en": r.respondida_en.isoformat()} if r else None
            ),
            "ultima_visita": resena.ultima_visita,
            "estado": resena.estado.value,
            "reportes_pendientes": resena.reportes_pendientes,
            "creada_en": resena.creada_en,
            "editada_en": resena.editada_en,
            "version": resena.version,
        }
        try:
            await upsert(self._session, ResenaModelo, valores)
        except IntegrityError as error:
            # Dos envíos simultáneos del mismo turista: el caso de uso no vio la otra reseña.
            if viola(error, UNA_POR_TURISTA):
                raise YaResenado(servicio=str(resena.servicio_id)) from error
            raise
