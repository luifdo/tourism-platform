from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.dependencies import get_reloj
from app.api.errors import register_error_handlers
from app.api.routers import admin, auth, health
from app.config import Settings, get_settings
from app.infrastructure.cache.valkey_revocacion import build_valkey_client
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.security.jwt_token_service import JwtTokenService, leer_llaves


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Sin llaves el servicio no arranca: LlavesJwtError explica qué archivo falta.
        private_pem, public_pem = leer_llaves(
            settings.jwt_private_key_path, settings.jwt_public_key_path
        )
        app.state.token_service = JwtTokenService(
            private_pem,
            public_pem,
            issuer=settings.jwt_issuer,
            ttl=timedelta(minutes=settings.jwt_access_token_ttl_minutes),
            reloj=get_reloj(),
        )
        app.state.engine = build_engine(settings.database_url)
        app.state.session_factory = build_session_factory(app.state.engine)
        app.state.valkey = build_valkey_client(settings.valkey_url)
        yield
        await app.state.valkey.aclose()
        await app.state.engine.dispose()

    app = FastAPI(title=settings.service_name, version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app


app = create_app()
