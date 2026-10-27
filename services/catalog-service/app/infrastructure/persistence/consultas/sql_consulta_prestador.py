"""Lectura del panel del prestador (implementa ConsultaPrestador), sin bloquear filas."""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.pagina_servicios_editables import PaginaServiciosEditables
from app.application.dto.servicio_editable import ServicioEditable
from app.application.dto.zona_resumen import ZonaResumen
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.infrastructure.persistence.modelos.atractivo_servicio import AtractivoServicioModelo
from app.infrastructure.persistence.modelos.prestador_perfil import PrestadorPerfilModelo
from app.infrastructure.persistence.modelos.zona import ZonaModelo
from app.infrastructure.persistence.repositorios.prestador_repository import perfil_desde_modelo
from app.infrastructure.persistence.repositorios.servicio_repository import (
    servicio_desde_modelo,
)


def _con_zona() -> Select[Any]:
    # La zona inactiva no se muestra, igual que en el catálogo público.
    return select(AtractivoServicioModelo, ZonaModelo.codigo, ZonaModelo.nombre).outerjoin(
        ZonaModelo,
        (ZonaModelo.id == AtractivoServicioModelo.zona_id) & ZonaModelo.activa,
    )


def _editable(fila: Any) -> ServicioEditable:
    modelo, codigo, nombre = fila
    zona = ZonaResumen(codigo=codigo, nombre=TextoTraducido(**nombre)) if codigo else None
    return ServicioEditable(servicio=servicio_desde_modelo(modelo), zona=zona)


class SqlConsultaPrestador:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def perfil_de_usuario(self, usuario_id: UUID) -> PrestadorPerfil | None:
        async with self._sesiones() as session:
            fila = await session.scalar(
                select(PrestadorPerfilModelo).where(PrestadorPerfilModelo.usuario_id == usuario_id)
            )
        return perfil_desde_modelo(fila) if fila else None

    async def servicios(
        self, prestador_id: UUID, pagina: int, tamano: int
    ) -> PaginaServiciosEditables:
        del_prestador = AtractivoServicioModelo.prestador_id == prestador_id
        async with self._sesiones() as session:
            total = await session.scalar(
                select(func.count()).select_from(AtractivoServicioModelo).where(del_prestador)
            )
            filas = (
                await session.execute(
                    _con_zona()
                    .where(del_prestador)
                    .order_by(AtractivoServicioModelo.creado_en.desc(), AtractivoServicioModelo.id)
                    .limit(tamano)
                    .offset((pagina - 1) * tamano)
                )
            ).all()
        return PaginaServiciosEditables(
            items=tuple(_editable(f) for f in filas), pagina=pagina, tamano=tamano, total=total or 0
        )

    async def servicio(self, servicio_id: UUID) -> ServicioEditable | None:
        async with self._sesiones() as session:
            fila = (
                await session.execute(_con_zona().where(AtractivoServicioModelo.id == servicio_id))
            ).first()
        return _editable(fila) if fila else None
