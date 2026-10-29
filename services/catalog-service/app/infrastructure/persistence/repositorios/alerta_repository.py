"""Repositorio de AlertaOficial (tabla `alerta_oficial`)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.modelos.alerta_oficial import AlertaOficialModelo
from app.infrastructure.persistence.repositorios.comun import upsert


def alerta_desde_modelo(fila: AlertaOficialModelo) -> AlertaOficial:
    """También lo usa el panel de la Entidad, que lee sin bloquear filas."""
    return AlertaOficial(
        id=fila.id,
        nivel=NivelAlerta(fila.nivel),
        mensaje=TextoTraducido(**fila.mensaje),
        entidad_usuario_id=fila.entidad_usuario_id,
        fecha_expiracion=fila.fecha_expiracion,
        creada_en=fila.creada_en,
        servicio_id=fila.servicio_id,
        zona_id=fila.zona_id,
        activa=fila.activa,
        version=fila.version,
    )


class SqlAlertaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, alerta_id: UUID) -> AlertaOficial | None:
        fila = await self._session.scalar(
            select(AlertaOficialModelo).where(AlertaOficialModelo.id == alerta_id).with_for_update()
        )
        return alerta_desde_modelo(fila) if fila else None

    async def contar_vigentes_de_zona(self, zona_id: UUID, ahora: datetime) -> int:
        return (
            await self._session.scalar(
                select(func.count())
                .select_from(AlertaOficialModelo)
                .where(
                    AlertaOficialModelo.zona_id == zona_id,
                    AlertaOficialModelo.activa,
                    AlertaOficialModelo.fecha_expiracion > ahora,
                )
            )
            or 0
        )

    async def guardar(self, alerta: AlertaOficial) -> None:
        await upsert(
            self._session,
            AlertaOficialModelo,
            {
                "id": alerta.id,
                "nivel": alerta.nivel.value,
                "mensaje": alerta.mensaje.a_dict(),
                "entidad_usuario_id": alerta.entidad_usuario_id,
                "servicio_id": alerta.servicio_id,
                "zona_id": alerta.zona_id,
                "fecha_expiracion": alerta.fecha_expiracion,
                "creada_en": alerta.creada_en,
                "activa": alerta.activa,
                "version": alerta.version,
            },
        )
