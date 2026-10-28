"""Consultas de lectura de reseñas (implementa ConsultaResenas).

Leen sin bloquear filas y con los índices de la migración 0001: `ix_resena_servicio`
(listas y resumen de un servicio), `ix_resena_turista` (mis reseñas), la PK de
`elegibilidad_resena` (pendientes) e `ix_servicio_dueno_prestador` (reseñas del prestador).
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.orden_resenas import OrdenResenas
from app.application.dto.pagina_resenas import PaginaResenas
from app.application.dto.promedio_aspecto import PromedioAspecto
from app.application.dto.resumen_servicio import ResumenServicio
from app.application.dto.servicio_pendiente import ServicioPendiente
from app.domain.entities.resena import Resena
from app.domain.value_objects.aspecto import Aspecto
from app.domain.value_objects.estado_resena import EstadoResena
from app.infrastructure.persistence.modelos.elegibilidad_resena import ElegibilidadResenaModelo
from app.infrastructure.persistence.modelos.resena import ResenaModelo
from app.infrastructure.persistence.modelos.servicio_dueno import ServicioDuenoModelo
from app.infrastructure.persistence.repositorios.resena_repository import resena_desde_modelo

R = ResenaModelo
_RECIENTE = (R.creada_en.desc(), R.id)
ORDEN = {
    OrdenResenas.RECIENTES: _RECIENTE,
    OrdenResenas.MEJORES: (R.puntuacion.desc(), *_RECIENTE),
    OrdenResenas.PEORES: (R.puntuacion.asc(), *_RECIENTE),
}
# Las que cuentan en el promedio: en revisión siguen contando, solo OCULTA no.
_CUENTAN = (EstadoResena.PUBLICADA.value, EstadoResena.EN_REVISION.value)

_RESUMEN = text(
    """
    SELECT count(*) AS total,
           round(avg(puntuacion), 2) AS promedio,
           count(*) FILTER (WHERE puntuacion = 1) AS p1,
           count(*) FILTER (WHERE puntuacion = 2) AS p2,
           count(*) FILTER (WHERE puntuacion = 3) AS p3,
           count(*) FILTER (WHERE puntuacion = 4) AS p4,
           count(*) FILTER (WHERE puntuacion = 5) AS p5
    FROM resena
    WHERE servicio_id = :servicio AND estado IN ('PUBLICADA', 'EN_REVISION')
    """
)
_ASPECTOS = text(
    """
    SELECT a.key AS aspecto, round(avg(a.value::int), 2) AS promedio, count(*) AS total
    FROM resena, jsonb_each_text(resena.aspectos) AS a
    WHERE servicio_id = :servicio AND estado IN ('PUBLICADA', 'EN_REVISION')
    GROUP BY a.key
    """
)


class SqlConsultaResenas:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def de_servicio(
        self, servicio_id: UUID, orden: OrdenResenas, pagina: int, tamano: int
    ) -> PaginaResenas:
        consulta = select(R).where(
            R.servicio_id == servicio_id, R.estado == EstadoResena.PUBLICADA.value
        )
        return await self._pagina(consulta, ORDEN[orden], pagina, tamano)

    async def resumen(self, servicio_id: UUID) -> ResumenServicio:
        async with self._sesiones() as session:
            fila = (await session.execute(_RESUMEN, {"servicio": servicio_id})).one()
            aspectos = (await session.execute(_ASPECTOS, {"servicio": servicio_id})).all()
        return ResumenServicio(
            servicio_id=servicio_id,
            total=fila.total,
            promedio=Decimal(fila.promedio) if fila.promedio is not None else None,
            distribucion={n: getattr(fila, f"p{n}") for n in range(1, 6)},
            aspectos={
                Aspecto(a.aspecto): PromedioAspecto(promedio=Decimal(a.promedio), total=a.total)
                for a in aspectos
            },
        )

    async def publica(self, resena_id: UUID) -> Resena | None:
        async with self._sesiones() as session:
            fila = await session.scalar(
                select(R).where(R.id == resena_id, R.estado == EstadoResena.PUBLICADA.value)
            )
        return resena_desde_modelo(fila) if fila else None

    async def del_turista(self, turista_id: UUID, pagina: int, tamano: int) -> PaginaResenas:
        return await self._pagina(
            select(R).where(R.turista_id == turista_id), _RECIENTE, pagina, tamano
        )

    async def pendientes(self, turista_id: UUID) -> list[ServicioPendiente]:
        e = ElegibilidadResenaModelo
        ya_resenado = select(R.id).where(
            R.turista_id == e.turista_id, R.servicio_id == e.servicio_id
        )
        async with self._sesiones() as session:
            filas = await session.execute(
                select(e.servicio_id, e.ultima_visita)
                .where(e.turista_id == turista_id, ~ya_resenado.exists())
                .order_by(e.ultima_visita.desc(), e.servicio_id)
            )
        return [ServicioPendiente(servicio_id=s, ultima_visita=f) for s, f in filas]

    async def dueno_de(self, servicio_id: UUID) -> UUID | None:
        async with self._sesiones() as session:
            return await session.scalar(
                select(ServicioDuenoModelo.prestador_usuario_id).where(
                    ServicioDuenoModelo.servicio_id == servicio_id
                )
            )

    async def del_prestador(
        self,
        prestador_usuario_id: UUID,
        servicio_id: UUID | None,
        sin_respuesta: bool,
        pagina: int,
        tamano: int,
    ) -> PaginaResenas:
        d = ServicioDuenoModelo
        consulta = (
            select(R)
            .join(d, d.servicio_id == R.servicio_id)
            .where(d.prestador_usuario_id == prestador_usuario_id, R.estado.in_(_CUENTAN))
        )
        if servicio_id is not None:
            consulta = consulta.where(R.servicio_id == servicio_id)
        if sin_respuesta:
            consulta = consulta.where(R.respuesta.is_(None))
        return await self._pagina(consulta, _RECIENTE, pagina, tamano)

    async def _pagina(
        self, consulta: Select[Any], orden: tuple[Any, ...], pagina: int, tamano: int
    ) -> PaginaResenas:
        async with self._sesiones() as session:
            total = await session.scalar(select(func.count()).select_from(consulta.subquery()))
            filas = await session.scalars(
                consulta.order_by(*orden).limit(tamano).offset((pagina - 1) * tamano)
            )
            items = [resena_desde_modelo(f) for f in filas]
        return PaginaResenas(items=items, pagina=pagina, tamano=tamano, total=total or 0)
