"""Repositorio de ReporteResena (tabla `reporte_resena`)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.reporte_resena import ReporteResena
from app.domain.errors import YaReportada
from app.domain.value_objects.identidad import Rol
from app.domain.value_objects.motivo_reporte import MotivoReporte
from app.infrastructure.persistence.modelos.reporte_resena import ReporteResenaModelo
from app.infrastructure.persistence.repositorios.comun import viola

UNO_POR_USUARIO = "uq_reporte_resena_usuario"
# Espacio propio del candado consultivo: no choca con los de otras tablas o migraciones.
CANDADO_REPORTES = 4_401


def reporte_desde_modelo(fila: ReporteResenaModelo) -> ReporteResena:
    """También la usa la cola de moderación."""
    return ReporteResena(
        id=fila.id,
        resena_id=fila.resena_id,
        usuario_id=fila.usuario_id,
        rol=Rol(fila.rol),
        motivo=MotivoReporte(fila.motivo),
        detalle=fila.detalle,
        es_dueno=fila.es_dueno,
        reportado_en=fila.reportado_en,
        resuelto_en=fila.resuelto_en,
    )


class SqlReporteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def agregar(self, reporte: ReporteResena) -> None:
        self._session.add(
            ReporteResenaModelo(
                id=reporte.id,
                resena_id=reporte.resena_id,
                usuario_id=reporte.usuario_id,
                rol=reporte.rol.value,
                motivo=reporte.motivo.value,
                detalle=reporte.detalle,
                es_dueno=reporte.es_dueno,
                reportado_en=reporte.reportado_en,
                resuelto_en=reporte.resuelto_en,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if viola(error, UNO_POR_USUARIO):
                raise YaReportada(resena=str(reporte.resena_id)) from error
            raise

    async def recientes_de_usuario(self, usuario_id: UUID, desde: datetime) -> list[datetime]:
        # Candado de transacción por usuario: dos reportes simultáneos del mismo usuario se
        # cuentan uno después del otro y no pasan juntos el límite.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:espacio, hashtext(:usuario))"),
            {"espacio": CANDADO_REPORTES, "usuario": str(usuario_id)},
        )
        m = ReporteResenaModelo
        return list(
            await self._session.scalars(
                select(m.reportado_en)
                .where(m.usuario_id == usuario_id, m.reportado_en > desde)
                .order_by(m.reportado_en)
            )
        )

    async def resolver_abiertos(self, resena_id: UUID, ahora: datetime) -> int:
        m = ReporteResenaModelo
        resultado = await self._session.execute(
            update(m)
            .where(m.resena_id == resena_id, m.resuelto_en.is_(None))
            .values(resuelto_en=ahora)
            .returning(m.id)
        )
        return len(resultado.all())
