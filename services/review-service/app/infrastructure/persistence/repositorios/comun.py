"""Utilidades compartidas por los repositorios SQLAlchemy de escritura.

* `obtener` bloquea la fila (`SELECT ... FOR UPDATE`): con varias réplicas, dos ediciones
  simultáneas de la misma reseña se ordenan y la segunda ve la versión nueva (409), en vez
  de pisar la primera.
* `guardar` es un upsert por llave primaria.
* Las reglas de unicidad (una reseña por turista y servicio, un reporte por usuario y
  reseña) las garantiza la base; `viola` reconoce cuál se incumplió para lanzar el error
  del dominio.
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert(session: AsyncSession, modelo: Any, valores: dict[str, Any]) -> None:
    llaves = [c.name for c in modelo.__table__.primary_key.columns]
    sentencia = insert(modelo).values(**valores)
    actualizar = {k: sentencia.excluded[k] for k in valores if k not in llaves}
    await session.execute(sentencia.on_conflict_do_update(index_elements=llaves, set_=actualizar))


def viola(error: IntegrityError, restriccion: str) -> bool:
    return restriccion in str(error.orig)
