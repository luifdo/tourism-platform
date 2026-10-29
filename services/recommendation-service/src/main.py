from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.application.ports.modelo_de_lenguaje import ModeloDeLenguaje
from src.application.responder_mensaje import ResponderMensaje
from src.application.verificar_salud import VerificarSalud
from src.config import Configuracion
from src.infrastructure.http import chat, health
from src.infrastructure.http.errores import registrar_manejadores
from src.infrastructure.llm.fabrica import crear_modelo
from src.infrastructure.persistence.base_de_datos import SondaPostgres, crear_motor
from src.infrastructure.persistence.registro_recomendaciones_pg import (
    RegistroRecomendacionesPostgres,
)
from src.infrastructure.persistence.sesiones_valkey import (
    LimiteValkey,
    SesionesValkey,
    SondaValkey,
    crear_cliente_valkey,
)
from src.infrastructure.tools.herramientas_plataforma import HerramientasPlataforma


def create_app(
    config: Configuracion | None = None, modelo: ModeloDeLenguaje | None = None
) -> FastAPI:
    """`modelo` deja a las pruebas inyectar un modelo con guion; si falta, lo elige LLM_PROVIDER."""
    config = config or Configuracion()
    # Ni el motor ni los clientes abren conexiones al crearse; lo hacen en la primera consulta.
    motor = crear_motor(config.db_url)
    valkey = crear_cliente_valkey(config.valkey_url)
    cliente_http = httpx.AsyncClient(timeout=config.herramientas_timeout_segundos)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        yield
        await cliente_http.aclose()
        await valkey.aclose()
        await motor.dispose()

    app = FastAPI(title="recommendation-service", version="1.0.0", lifespan=ciclo_de_vida)
    app.state.verificar_salud = VerificarSalud(SondaPostgres(motor), SondaValkey(valkey))
    app.state.responder_mensaje = ResponderMensaje(
        modelo=modelo or crear_modelo(config),
        herramientas=HerramientasPlataforma(
            cliente_http, config.catalog_url, config.booking_url, config.review_url
        ),
        sesiones=SesionesValkey(valkey),
        registro=RegistroRecomendacionesPostgres(motor),
        limite=LimiteValkey(
            valkey,
            maximo=config.chat_limite_mensajes,
            ventana=timedelta(seconds=config.chat_limite_ventana_segundos),
        ),
        reloj=lambda: datetime.now(UTC),
        timeout_segundos=config.chat_timeout_segundos,
    )
    registrar_manejadores(app)
    app.include_router(health.router)
    app.include_router(chat.router)
    # Expone GET /metrics en formato Prometheus (RNF-12).
    Instrumentator().instrument(app).expose(app)
    return app


app = create_app()
