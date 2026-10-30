from httpx import ASGITransport, AsyncClient

from src.config import Configuracion
from src.infrastructure.persistence.base_de_datos import SondaPostgres, crear_motor
from src.infrastructure.persistence.sesiones_valkey import SondaValkey, crear_cliente_valkey
from src.main import create_app

# Puertos donde no escucha nada.
DB_CAIDA = "postgresql+psycopg://turismo:turismo@localhost:1/recommendation_db"
VALKEY_CAIDO = "redis://localhost:1/0"


async def _get_health(config: Configuracion):
    transporte = ASGITransport(app=create_app(config))
    async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
        return await cliente.get("/health")


async def test_health_200_con_postgres_y_valkey_reales(motor, valkey, urls_reales):
    db_url, valkey_url = urls_reales

    respuesta = await _get_health(Configuracion(db_url=db_url, valkey_url=valkey_url))

    assert respuesta.status_code == 200
    assert respuesta.json()["checks"] == {"database": "up", "valkey": "up"}


async def test_health_503_si_valkey_no_responde(motor, urls_reales):
    db_url, _ = urls_reales

    respuesta = await _get_health(Configuracion(db_url=db_url, valkey_url=VALKEY_CAIDO))

    assert respuesta.status_code == 503
    assert respuesta.json()["checks"] == {"database": "up", "valkey": "down"}


async def test_health_503_si_postgres_no_responde(valkey, urls_reales):
    _, valkey_url = urls_reales

    respuesta = await _get_health(Configuracion(db_url=DB_CAIDA, valkey_url=valkey_url))

    assert respuesta.status_code == 503
    assert respuesta.json()["checks"] == {"database": "down", "valkey": "up"}


async def test_las_sondas_devuelven_false_en_lugar_de_fallar():
    motor = crear_motor(DB_CAIDA)
    valkey = crear_cliente_valkey(VALKEY_CAIDO)

    assert await SondaPostgres(motor).ping() is False
    assert await SondaValkey(valkey).ping() is False

    await valkey.aclose()
    await motor.dispose()
