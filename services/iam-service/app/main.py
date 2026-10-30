from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.dependencies import get_reloj
from app.api.errors import register_error_handlers
from app.api.middleware.correlacion_middleware import CorrelacionMiddleware
from app.api.openapi import esquema_openapi
from app.api.routers import admin, auth, health, internal, perfil, prestador
from app.api.segundo_plano import TareasSegundoPlano
from app.config import Settings, get_settings
from app.infrastructure.cache.valkey_revocacion import build_valkey_client
from app.infrastructure.correo.enviador_smtp import EnviadorSmtp
from app.infrastructure.observabilidad.configurar_logs import configurar_logs
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_token_service import JwtTokenService, leer_llaves
from app.infrastructure.storage.almacen_documentos_s3 import AlmacenDocumentosS3

_ESPERA_TAREAS_AL_APAGAR = 15.0


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configurar_logs(settings.service_name, settings.log_level)

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
        app.state.password_hasher = Argon2PasswordHasher(
            settings.argon2_concurrencia_maxima, settings.argon2_espera_maxima_segundos
        )
        app.state.engine = build_engine(settings.database_url)
        app.state.session_factory = build_session_factory(app.state.engine)
        app.state.valkey = build_valkey_client(settings.valkey_url)
        app.state.almacen_documentos = AlmacenDocumentosS3(
            endpoint_interno=settings.s3_endpoint_url,
            endpoint_publico=settings.s3_endpoint_publico,
            region=settings.s3_region,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
        )
        app.state.enviador_correo = EnviadorSmtp(
            host=settings.smtp_host,
            puerto=settings.smtp_port,
            remitente=settings.smtp_from,
            usuario=settings.smtp_usuario,
            clave=settings.smtp_password,
            starttls=settings.smtp_tls,
            timeout_segundos=settings.smtp_timeout_seconds,
        )
        app.state.tareas_segundo_plano = TareasSegundoPlano()
        yield
        # Antes de cerrar Valkey y la base, que estas tareas usan.
        await app.state.tareas_segundo_plano.esperar(timeout_segundos=_ESPERA_TAREAS_AL_APAGAR)
        await app.state.valkey.aclose()
        await app.state.engine.dispose()

    app = FastAPI(title=settings.service_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelacionMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(perfil.router)
    app.include_router(prestador.router)
    app.include_router(internal.router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    app.openapi = lambda: esquema_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
