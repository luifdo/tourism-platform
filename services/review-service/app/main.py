from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.errores.manejador_errores import registrar_manejadores
from app.api.middleware.correlacion_middleware import CorrelacionMiddleware
from app.api.routers import health
from app.config import Settings, get_settings
from app.infrastructure.observabilidad.configurar_logs import configurar_logs
from app.infrastructure.persistence.database import build_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configurar_logs(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings.database_url)
        app.state.engine = engine
        yield
        await engine.dispose()

    app = FastAPI(title=settings.service_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelacionMiddleware)
    registrar_manejadores(app)
    for modulo in (health,):
        app.include_router(modulo.router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app


app = create_app()
