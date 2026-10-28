from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.errores.manejador_errores import registrar_manejadores
from app.api.middleware.correlacion_middleware import CorrelacionMiddleware
from app.api.routers import health, resenas_turista
from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.config import Settings, get_settings
from app.infrastructure.observabilidad.configurar_logs import configurar_logs
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.idempotencia_postgres import IdempotenciaPostgres
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.infrastructure.reloj import RelojSistema


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configurar_logs(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings.database_url)
        sesiones = build_session_factory(engine)
        reloj = RelojSistema()
        app.state.engine = engine
        app.state.reloj = reloj
        app.state.unidad_de_trabajo = lambda: SqlUnidadDeTrabajo(sesiones)
        app.state.auditor_accesos = RegistrarAccesoDenegado(app.state.unidad_de_trabajo, reloj)
        app.state.idempotencia = IdempotenciaPostgres(sesiones)
        yield
        await engine.dispose()

    app = FastAPI(title=settings.service_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelacionMiddleware)
    registrar_manejadores(app)
    for modulo in (health, resenas_turista):
        app.include_router(modulo.router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app


app = create_app()
