"""Conexión a booking_db con SQLAlchemy asíncrono y asyncpg.

* El **motor** (`AsyncEngine`) se crea una sola vez al arrancar la app y mantiene un *pool*
  de conexiones abiertas que se reutilizan entre peticiones.
* Cada **sesión** (`AsyncSession`) es una transacción: la abre la unidad de trabajo
  (paso 5.2e) y la cierra al terminar, devolviendo la conexión al pool.
* La sesión de base de datos trabaja en UTC. Postgres guarda los `timestamptz` como un instante
  sin ambigüedad; los repositorios los convierten a hora de Bogotá al pasarlos al dominio.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config import Configuracion

NOMBRE_APLICACION = "booking-service"  # aparece en pg_stat_activity: se sabe quién tiene cada conexión


def crear_motor(config: Configuracion) -> AsyncEngine:
    """Crea el motor sin conectarse todavía: la primera conexión se abre con la primera consulta."""
    return create_async_engine(
        config.database_url,
        pool_size=config.db_pool_tamano,
        max_overflow=config.db_pool_extra,
        pool_timeout=config.db_pool_espera_s,
        # Antes de prestar una conexión del pool, comprueba que siga viva (p. ej. tras un reinicio de Postgres).
        pool_pre_ping=True,
        connect_args={"server_settings": {"application_name": NOMBRE_APLICACION, "timezone": "UTC"}},
    )


def fabrica_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: después del COMMIT se pueden seguir leyendo los datos ya cargados
    # (por ejemplo, para armar los eventos) sin otra consulta a la base.
    return async_sessionmaker(motor, expire_on_commit=False, autoflush=False)


async def verificar_conexion(motor: AsyncEngine) -> bool:
    """`SELECT 1`: lo usará /health para que Kubernetes no envíe tráfico si la base no responde."""
    try:
        async with motor.connect() as conexion:
            await conexion.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
