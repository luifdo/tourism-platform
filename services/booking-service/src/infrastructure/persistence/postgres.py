"""Repositorios de booking_db en Postgres (SQLAlchemy Core + asyncpg).

Cada repositorio recibe la conexión (o sesión) de la transacción en curso: la abre y la cierra
la unidad de trabajo (paso 5.2e), así todo lo que hace un caso de uso se confirma o se deshace junto.
Los repositorios solo traducen filas <-> objetos del dominio; las reglas viven en el dominio.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from domain.servicio import ServicioRef
from infrastructure.persistence.tablas import servicio_ref

Ejecutor = AsyncConnection | AsyncSession  # ambos tienen `execute`; las pruebas usan una conexión


# ---------- servicio_ref ----------

_COLUMNAS_SERVICIO = (
    "servicio_id", "prestador_id", "prestador_usuario_id",
    "capacidad_aforo_diario", "tarifa_base", "activo", "version",
)


def _servicio(fila: RowMapping) -> ServicioRef:
    return ServicioRef(**{c: fila[c] for c in _COLUMNAS_SERVICIO})


class RepositorioServiciosPostgres:
    def __init__(self, db: Ejecutor):
        self._db = db

    async def leer(self, servicio_id: UUID) -> ServicioRef | None:
        fila = (await self._db.execute(
            select(servicio_ref).where(servicio_ref.c.servicio_id == servicio_id)
        )).mappings().first()
        return _servicio(fila) if fila else None

    async def guardar_si_mas_nuevo(self, servicio: ServicioRef) -> bool:
        """Una sola sentencia, sin leer antes:

            INSERT ... ON CONFLICT (servicio_id) DO UPDATE SET ...
            WHERE servicio_ref.version < EXCLUDED.version
            RETURNING servicio_id

        * Si el servicio no existe, lo inserta.
        * Si existe, lo reemplaza solo si la versión que llega es mayor (la misma regla que
          `ServicioRef.reemplaza_a`). Si no, no toca nada y `RETURNING` no devuelve fila.
        * Si dos réplicas reciben dos eventos del mismo servicio a la vez, Postgres hace esperar
          a la segunda hasta que la primera confirme y compara contra lo ya guardado: siempre
          queda la versión mayor. Con "leer, comparar y guardar" podía ganar la menor.
        """
        valores = {c: getattr(servicio, c) for c in _COLUMNAS_SERVICIO}
        sentencia = insert(servicio_ref).values(**valores)
        sentencia = sentencia.on_conflict_do_update(
            index_elements=[servicio_ref.c.servicio_id],
            set_={
                **{c: sentencia.excluded[c] for c in _COLUMNAS_SERVICIO if c != "servicio_id"},
                "actualizado_en": func.now(),
            },
            where=servicio_ref.c.version < sentencia.excluded.version,
        ).returning(servicio_ref.c.servicio_id)
        return (await self._db.execute(sentencia)).first() is not None
