import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

RAIZ = Path(__file__).resolve().parents[2]


def test_bajar_y_subir_migraciones(alembic_cfg: Config) -> None:
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


def test_dos_pods_migrando_a_la_vez_no_chocan(alembic_cfg: Config, database_url: str) -> None:
    """Como dos initContainers que arrancan juntos: el candado hace que uno espere al otro."""
    command.downgrade(alembic_cfg, "base")

    def migrar() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=RAIZ,
            env=os.environ | {"DATABASE_URL": database_url},
            capture_output=True,
            text=True,
            timeout=120,
        )

    with ThreadPoolExecutor(2) as hilos:
        resultados = list(hilos.map(lambda _: migrar(), range(2)))
    assert [r.returncode for r in resultados] == [0, 0], [r.stderr[-2000:] for r in resultados]
    command.upgrade(alembic_cfg, "head")  # ya está en head: no hace nada


async def test_tablas_e_indices(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        tablas = set(
            await conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        )
        indices = set(
            await conn.scalars(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
        )
    assert {
        "resena",
        "reporte_resena",
        "elegibilidad_resena",
        "servicio_dueno",
        "evento_procesado",
        "outbox",
        "idempotencia",
    } <= tablas
    assert {
        "uq_resena_turista_servicio",
        "uq_reporte_resena_usuario",
        "ix_resena_moderacion",
        "ix_reporte_usuario",
        "ix_outbox_pendientes",
        "ix_evento_procesado_fecha",
        "ix_idempotencia_expira",
    } <= indices
