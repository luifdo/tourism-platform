"""Repositorio de PrestadorPerfil (tabla `prestador_perfil`)."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.infrastructure.persistence.modelos.prestador_perfil import PrestadorPerfilModelo
from app.infrastructure.persistence.repositorios.comun import texto_o_none, upsert


def perfil_desde_modelo(fila: PrestadorPerfilModelo) -> PrestadorPerfil:
    """También lo usan las consultas de lectura, que leen sin bloquear filas."""
    return PrestadorPerfil(
        id=fila.id,
        usuario_id=fila.usuario_id,
        razon_social=fila.razon_social,
        telefono=fila.telefono,
        direccion=fila.direccion,
        politica_cancelacion=texto_o_none(fila.politica_cancelacion),
        activo=fila.activo,
        version=fila.version,
        estado_iam_en=fila.estado_iam_en,
    )


class SqlPrestadorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def obtener(self, prestador_id: UUID) -> PrestadorPerfil | None:
        return await self._uno(PrestadorPerfilModelo.id == prestador_id)

    async def obtener_por_usuario(self, usuario_id: UUID) -> PrestadorPerfil | None:
        return await self._uno(PrestadorPerfilModelo.usuario_id == usuario_id)

    async def guardar(self, perfil: PrestadorPerfil) -> None:
        await upsert(
            self._session,
            PrestadorPerfilModelo,
            {
                "id": perfil.id,
                "usuario_id": perfil.usuario_id,
                "razon_social": perfil.razon_social,
                "telefono": perfil.telefono,
                "direccion": perfil.direccion,
                "politica_cancelacion": (
                    perfil.politica_cancelacion.a_dict() if perfil.politica_cancelacion else None
                ),
                "activo": perfil.activo,
                "version": perfil.version,
                "estado_iam_en": perfil.estado_iam_en,
                "actualizado_en": func.now(),
            },
            salvo_si_es_mas_nueva="estado_iam_en",
        )

    async def _uno(self, condicion: Any) -> PrestadorPerfil | None:
        fila = await self._session.scalar(
            select(PrestadorPerfilModelo).where(condicion).with_for_update()
        )
        return perfil_desde_modelo(fila) if fila else None
