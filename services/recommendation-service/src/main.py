from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.application.verificar_salud import VerificarSalud
from src.config import Configuracion
from src.infrastructure.http import health
from src.infrastructure.persistence.base_de_datos import SondaPostgres, crear_motor
from src.infrastructure.persistence.sesiones_valkey import SondaValkey, crear_cliente_valkey


def create_app(config: Configuracion | None = None) -> FastAPI:
    config = config or Configuracion()
    # Ni el motor ni el cliente abren conexiones al crearse; lo hacen en la primera consulta.
    motor = crear_motor(config.db_url)
    valkey = crear_cliente_valkey(config.valkey_url)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        yield
        await valkey.aclose()
        await motor.dispose()

    app = FastAPI(title="recommendation-service", version="1.0.0", lifespan=ciclo_de_vida)
    app.state.verificar_salud = VerificarSalud(SondaPostgres(motor), SondaValkey(valkey))
    app.include_router(health.router)
    # Expone GET /metrics en formato Prometheus (RNF-12).
    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
