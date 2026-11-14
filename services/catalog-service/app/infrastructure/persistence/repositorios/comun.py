"""Utilidades compartidas por los repositorios SQLAlchemy de escritura.

* `obtener` bloquea la fila (`SELECT ... FOR UPDATE`): con varias réplicas, dos ediciones
  simultáneas del mismo registro se ordenan y la segunda ve la versión nueva (409), en vez
  de pisar la primera.
* `guardar` es un upsert por llave primaria; las columnas generadas no se escriben.
* Las filas alimentadas por eventos usan `salvo_si_es_mas_nueva`: si dos eventos de una
  fila que aún no existe se procesan a la vez, ninguno tiene fila que bloquear y los dos la
  insertan; la base deja ganar al más nuevo, sin importar cuál confirma primero.
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects.texto_traducido import TextoTraducido


def texto_o_none(valor: dict[str, str] | None) -> TextoTraducido | None:
    return TextoTraducido(**valor) if valor else None


async def upsert(
    session: AsyncSession,
    modelo: Any,
    valores: dict[str, Any],
    salvo_si_es_mas_nueva: str | None = None,
) -> None:
    """`salvo_si_es_mas_nueva`: columna con el momento del último evento; si la fila que ya
    está en la base es más nueva que la que se escribe, no se toca. Con el mismo momento sí
    se escribe (p. ej. una edición del perfil que no cambia su estado en iam)."""
    llaves = [c.name for c in modelo.__table__.primary_key.columns]
    sentencia = insert(modelo).values(**valores)
    actualizar = {k: sentencia.excluded[k] for k in valores if k not in llaves}
    donde = None
    if salvo_si_es_mas_nueva is not None:
        actual = modelo.__table__.c[salvo_si_es_mas_nueva]
        donde = actual.is_(None) | (actual <= sentencia.excluded[salvo_si_es_mas_nueva])
    await session.execute(
        sentencia.on_conflict_do_update(index_elements=llaves, set_=actualizar, where=donde)
    )
