"""Composición del booking-service: conecta cada puerto con su adaptador y crea la app FastAPI.

Ejecución local (desde services/booking-service):
    uvicorn main:app --app-dir src --port 8003 --reload                    # modo memoria (demo)

Contra Postgres (primero `python scripts/postgres_pruebas.py subir` y `alembic upgrade head`):
    $env:MODO_PERSISTENCIA="postgres"; uvicorn main:app --app-dir src --port 8003
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI

from application.base import Contexto
from config import Configuracion
from infrastructure.http import demo, operacion, rutas
from infrastructure.http.errores import registrar_manejadores
from infrastructure.messaging.memoria import PublicadorMemoria
from infrastructure.persistence.db import crear_motor, fabrica_sesiones
from infrastructure.persistence.idempotencia_memoria import AlmacenIdempotenciaMemoria
from infrastructure.persistence.memoria import AlmacenMemoria, fabrica_memoria
from infrastructure.persistence.postgres import fabrica_postgres
from infrastructure.reloj import RelojSistema


@dataclass
class Contenedor:
    ctx: Contexto
    idempotencia: Any
    publicador: Any
    extras: dict[str, Any] = field(default_factory=dict)


def contenedor_memoria(config: Configuracion, reloj: Any = None) -> Contenedor:
    publicador = PublicadorMemoria()
    ctx = Contexto(
        fabrica_memoria(AlmacenMemoria()), publicador, reloj or RelojSistema(), config.plazo_respuesta_horas
    )
    return Contenedor(ctx, AlmacenIdempotenciaMemoria(), publicador)


def contenedor_postgres(config: Configuracion, reloj: Any = None) -> Contenedor:
    """booking_db real. Los eventos y la idempotencia siguen en memoria hasta los pasos 5.3 y 5.4."""
    motor = crear_motor(config)  # no se conecta todavía: la primera conexión llega con la primera consulta
    publicador = PublicadorMemoria()
    ctx = Contexto(
        fabrica_postgres(fabrica_sesiones(motor)), publicador, reloj or RelojSistema(), config.plazo_respuesta_horas
    )
    return Contenedor(ctx, AlmacenIdempotenciaMemoria(), publicador, extras={"motor": motor})


def crear_app(config: Configuracion | None = None, contenedor: Contenedor | None = None) -> FastAPI:
    config = config or Configuracion()
    if contenedor is None:
        crear = contenedor_postgres if config.modo_persistencia == "postgres" else contenedor_memoria
        contenedor = crear(config)
    con_demo = config.modo_persistencia == "memoria" and config.datos_demo

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        if con_demo:
            await demo.cargar_datos_demo(contenedor)
        yield
        if motor := contenedor.extras.get("motor"):
            await motor.dispose()  # cierra las conexiones del pool al apagar el pod

    app = FastAPI(
        title="booking-service — Reservas & Cupos (Módulo 3)",
        version="0.1.0",
        description=demo.DESCRIPCION if con_demo else "Contrato: contracts/openapi/booking.yaml",
        lifespan=ciclo_de_vida,
    )
    app.state.contenedor = contenedor
    registrar_manejadores(app)
    operacion.registrar_metricas(app)
    app.include_router(rutas.router)
    app.include_router(operacion.router)
    if con_demo:
        app.include_router(demo.router)
    return app


app = crear_app()
