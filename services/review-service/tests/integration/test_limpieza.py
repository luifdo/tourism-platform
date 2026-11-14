"""Limpieza diaria del worker: solo lo vencido o viejo, nada más."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.use_cases.limpiar_registros_vencidos import LimpiarRegistrosVencidos
from app.infrastructure.persistence.repositorios.registros_vencidos import SqlRegistrosVencidos
from app.infrastructure.reloj import RelojSistema


async def test_borra_solo_lo_vencido(
    engine: AsyncEngine, sesiones: async_sessionmaker[AsyncSession]
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO idempotencia (clave, expira_en) VALUES"
                " ('vencida', now() - interval '1 minute'),"
                " ('vigente', now() + interval '1 hour')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO evento_procesado (event_id, consumidor, procesado_en) VALUES"
                " (:viejo, 'review.elegibilidad', now() - interval '31 days'),"
                " (:reciente, 'review.elegibilidad', now() - interval '29 days')"
            ),
            {"viejo": uuid4(), "reciente": uuid4()},
        )

    limpieza = LimpiarRegistrosVencidos(
        SqlRegistrosVencidos(sesiones), RelojSistema(), timedelta(days=30)
    )
    assert await limpieza.execute() == (1, 1)
    assert await limpieza.execute() == (0, 0)  # repetirla no hace daño

    async with engine.connect() as conn:
        claves = list(await conn.scalars(text("SELECT clave FROM idempotencia")))
        eventos = await conn.scalar(text("SELECT count(*) FROM evento_procesado"))
    assert (claves, eventos) == (["vigente"], 1)
