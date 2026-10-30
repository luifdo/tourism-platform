"""La bitácora es de solo inserción, con el rol de la app (RNF-10, C-03, C-04, Lab §6.1).

Cada sentencia rechazada corre en un SAVEPOINT y la prueba completa se deshace (`connection`),
así que un TRUNCATE que pasara por error tampoco borraría nada de la base de desarrollo.

Si el rol es dueño de la tabla o superusuario, como en docker-compose.dev.yml, el REVOKE no le
aplica y quien rechaza es el trigger; con otro rol, puede rechazar primero el REVOKE.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import get_settings

pytestmark = pytest.mark.db

INSERTAR = text(
    """
    INSERT INTO bitacora_auditoria (event_id, accion, resultado, servicio_origen)
    VALUES (:event_id, 'PRUEBA_INMUTABLE', 'Exito', 'pruebas')
    ON CONFLICT (event_id) DO NOTHING
    """
)
ACCION = text("SELECT accion FROM bitacora_auditoria WHERE event_id = :event_id")


@pytest.fixture
async def event_id(connection: AsyncConnection) -> uuid.UUID:
    # Con la tabla vacía, UPDATE y DELETE no tocarían filas y el trigger por fila no se dispararía.
    event_id = uuid.uuid4()
    await connection.execute(INSERTAR, {"event_id": event_id})
    return event_id


async def test_las_pruebas_corren_con_el_rol_de_la_app(connection: AsyncConnection) -> None:
    assert await connection.scalar(text("SELECT current_user")) == get_settings().db_app_role


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE bitacora_auditoria SET accion = 'ALTERADA' WHERE event_id = :event_id",
        "DELETE FROM bitacora_auditoria WHERE event_id = :event_id",
        "TRUNCATE bitacora_auditoria",
    ],
    ids=["UPDATE", "DELETE", "TRUNCATE"],
)
async def test_la_sentencia_falla_y_la_fila_sigue_igual(
    connection: AsyncConnection, event_id: uuid.UUID, sentencia: str
) -> None:
    parametros = {"event_id": event_id} if ":event_id" in sentencia else {}

    with pytest.raises(DBAPIError, match="solo inserción|permission denied"):
        async with connection.begin_nested():
            await connection.execute(text(sentencia), parametros)

    assert await connection.scalar(ACCION, {"event_id": event_id}) == "PRUEBA_INMUTABLE"


async def test_on_conflict_do_nothing_sigue_funcionando(
    connection: AsyncConnection, event_id: uuid.UUID
) -> None:
    repetido = await connection.execute(INSERTAR, {"event_id": event_id})
    nuevo = await connection.execute(INSERTAR, {"event_id": uuid.uuid4()})

    assert repetido.rowcount == 0
    assert nuevo.rowcount == 1
    filas = await connection.scalar(
        text("SELECT count(*) FROM bitacora_auditoria WHERE event_id = :event_id"),
        {"event_id": event_id},
    )
    assert filas == 1
