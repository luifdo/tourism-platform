from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from valkey.asyncio import Valkey

from app.api.errores.manejador_errores import registrar_manejadores
from app.api.middleware.correlacion_middleware import CorrelacionMiddleware
from app.api.routers import (
    alertas,
    alertas_entidad,
    analitica,
    busqueda,
    geocodificacion,
    health,
    imagenes,
    intenciones_visita,
    mapa,
    metricas_prestador,
    perfil_prestador,
    servicios,
    servicios_prestador,
    zonas,
    zonas_entidad,
)
from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.config import Settings, get_settings
from app.infrastructure.cache.cache_versionada import CacheVersionada
from app.infrastructure.cache.consulta_capacidad_en_cache import ConsultaCapacidadEnCache
from app.infrastructure.cache.consulta_mapa_en_cache import ConsultaMapaEnCache
from app.infrastructure.cache.consulta_servicios_en_cache import ConsultaServiciosEnCache
from app.infrastructure.cache.deduplicador_visitas_valkey import DeduplicadorVisitasValkey
from app.infrastructure.cache.geocodificador_en_cache import GeocodificadorEnCache
from app.infrastructure.cache.idempotencia_valkey import IdempotenciaValkey
from app.infrastructure.clients.limitador_por_segundo import LimitadorPorSegundo
from app.infrastructure.clients.nominatim_geocodificador import NominatimGeocodificador
from app.infrastructure.observabilidad.configurar_logs import configurar_logs
from app.infrastructure.persistence.consultas.sql_consulta_alertas import SqlConsultaAlertas
from app.infrastructure.persistence.consultas.sql_consulta_analitica import SqlConsultaAnalitica
from app.infrastructure.persistence.consultas.sql_consulta_capacidad import SqlConsultaCapacidad
from app.infrastructure.persistence.consultas.sql_consulta_mapa import SqlConsultaMapa
from app.infrastructure.persistence.consultas.sql_consulta_prestador import SqlConsultaPrestador
from app.infrastructure.persistence.consultas.sql_consulta_servicios import SqlConsultaServicios
from app.infrastructure.persistence.consultas.sql_consulta_zonas import SqlConsultaZonas
from app.infrastructure.persistence.consultas.sql_contador_intenciones import (
    SqlContadorIntenciones,
)
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.infrastructure.reloj import RelojSistema
from app.infrastructure.storage.almacen_imagenes_s3 import AlmacenImagenesS3


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configurar_logs(settings.service_name, settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(settings.database_url)
        sesiones = build_session_factory(engine)
        # Tiempos cortos: si Valkey se cae, la búsqueda sigue sin caché casi sin demora.
        valkey = Valkey.from_url(
            settings.valkey_url,
            socket_timeout=settings.valkey_timeout_seconds,
            socket_connect_timeout=settings.valkey_timeout_seconds,
        )
        nominatim = httpx.AsyncClient(
            base_url=settings.nominatim_url,
            headers={"User-Agent": settings.nominatim_user_agent},
            timeout=settings.nominatim_timeout_seconds,
        )
        reloj = RelojSistema()
        app.state.engine = engine
        app.state.reloj = reloj
        app.state.consulta_servicios = ConsultaServiciosEnCache(
            SqlConsultaServicios(sesiones), valkey
        )
        app.state.consulta_zonas = SqlConsultaZonas(sesiones)
        app.state.consulta_alertas = SqlConsultaAlertas(sesiones)
        app.state.consulta_mapa = ConsultaMapaEnCache(SqlConsultaMapa(sesiones), valkey)
        app.state.consulta_prestador = SqlConsultaPrestador(sesiones)
        app.state.contador_intenciones = SqlContadorIntenciones(sesiones)
        app.state.consulta_analitica = SqlConsultaAnalitica(sesiones)
        app.state.deduplicador_visitas = DeduplicadorVisitasValkey(
            valkey, settings.intencion_visita_secreto
        )
        app.state.consulta_capacidad = ConsultaCapacidadEnCache(
            SqlConsultaCapacidad(sesiones, reloj), valkey
        )
        app.state.unidad_de_trabajo = lambda: SqlUnidadDeTrabajo(sesiones)
        app.state.auditor_accesos = RegistrarAccesoDenegado(app.state.unidad_de_trabajo, reloj)
        app.state.invalidador_cache = CacheVersionada(valkey)
        app.state.idempotencia = IdempotenciaValkey(valkey)
        app.state.almacen_imagenes = AlmacenImagenesS3(
            endpoint_publico=settings.s3_endpoint_publico,
            region=settings.s3_region,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket_imagenes,
            url_publica_base=settings.imagenes_url_publica,
            reloj=reloj,
        )
        app.state.geocodificador = GeocodificadorEnCache(
            NominatimGeocodificador(
                nominatim,
                LimitadorPorSegundo(valkey, "catalog:nominatim:turno"),
                settings.nominatim_email,
            ),
            valkey,
        )
        yield
        await nominatim.aclose()
        await valkey.aclose()
        await engine.dispose()

    app = FastAPI(title=settings.service_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelacionMiddleware)
    registrar_manejadores(app)
    for modulo in (
        health,
        servicios,
        busqueda,
        zonas,
        zonas_entidad,
        alertas,
        alertas_entidad,
        mapa,
        analitica,
        intenciones_visita,
        metricas_prestador,
        servicios_prestador,
        perfil_prestador,
        imagenes,
        geocodificacion,
    ):
        app.include_router(modulo.router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app


app = create_app()
