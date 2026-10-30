from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.dto.respuesta_guardada import RespuestaGuardada
from app.infrastructure.persistence.idempotencia_postgres import IdempotenciaPostgres

RESPUESTA = RespuestaGuardada(201, b'{"id": "x"}', {"etag": '"1"'})


def clave() -> str:
    return f"idem:review:{uuid4()}"


async def vencer(engine: AsyncEngine, c: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE idempotencia SET expira_en = now() - interval '1 second' WHERE clave = :c"
            ),
            {"c": c},
        )


async def test_reserva_y_luego_devuelve_la_respuesta(
    sesiones: async_sessionmaker[AsyncSession],
) -> None:
    almacen, c = IdempotenciaPostgres(sesiones), clave()
    assert await almacen.reservar(c) is True
    assert await almacen.reservar(c) is False  # en proceso
    await almacen.guardar(c, RESPUESTA)
    assert await almacen.reservar(c) == RESPUESTA


async def test_liberar_permite_reintentar(sesiones: async_sessionmaker[AsyncSession]) -> None:
    almacen, c = IdempotenciaPostgres(sesiones), clave()
    await almacen.reservar(c)
    await almacen.liberar(c)
    assert await almacen.reservar(c) is True


async def test_una_reserva_vencida_se_retoma(
    sesiones: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    """El pod murió a mitad: pasados 60 s, el reintento se ejecuta."""
    almacen, c = IdempotenciaPostgres(sesiones), clave()
    await almacen.reservar(c)
    await vencer(engine, c)
    assert await almacen.reservar(c) is True
    assert await almacen.reservar(c) is False


async def test_la_respuesta_vence_a_las_48_horas(
    sesiones: async_sessionmaker[AsyncSession], engine: AsyncEngine
) -> None:
    almacen, c = IdempotenciaPostgres(sesiones), clave()
    await almacen.reservar(c)
    await almacen.guardar(c, RESPUESTA)
    async with engine.connect() as conn:
        horas = await conn.scalar(
            text("SELECT extract(epoch FROM expira_en - now()) / 3600 FROM idempotencia")
        )
    assert 47.9 < float(horas) <= 48
    await vencer(engine, c)
    assert await almacen.reservar(c) is True
