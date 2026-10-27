"""Worker de catalog-service: trabajo en segundo plano, separado de la API.

Corre con la misma imagen y otro comando (`python -m app.worker`), en su propio Deployment.
Así la publicación de eventos y los consumidores no compiten con las peticiones de los
turistas, y los reinicios o el escalado de la API no los interrumpen.

* Relay del outbox → `turismo.eventos`.
* Consumidor `catalog.prestadores` (`prestador.aprobado`, `prestador.suspendido`).
* Consumidor `catalog.demanda` (`reserva.*` → proyección de reservas).
* Consumidor `catalog.calificaciones` (`resena.publicada`, `resena.ocultada` → promedio).
* Consumidor `catalog.disponibilidad` (`disponibilidad.actualizada` → cupos por día).
* Consumidor `catalog.notificaciones` (`reserva.*` → correos al turista o al prestador).
* Limpieza diaria de la disponibilidad de días pasados.

Expone sus métricas en `WORKER_METRICS_PORT` (/metrics), que también sirve de sonda de vida.
"""

import asyncio
import contextlib
import logging
import signal
from datetime import timedelta

import httpx
from prometheus_client import start_http_server
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from valkey.asyncio import Valkey

from app.application.ports.invalidador_cache import InvalidadorCache
from app.application.use_cases.aplicar_disponibilidad import AplicarDisponibilidad
from app.application.use_cases.aplicar_evento_resena import AplicarEventoResena
from app.application.use_cases.aplicar_evento_reserva import AplicarEventoReserva
from app.application.use_cases.aplicar_prestador_aprobado import AplicarPrestadorAprobado
from app.application.use_cases.aplicar_prestador_suspendido import (
    AplicarPrestadorSuspendido,
)
from app.application.use_cases.limpiar_disponibilidad_pasada import LimpiarDisponibilidadPasada
from app.application.use_cases.notificar_reserva import NotificarReserva
from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.config import Settings, get_settings
from app.infrastructure.cache.cache_versionada import CacheVersionada
from app.infrastructure.clients.directorio_usuarios_iam import DirectorioUsuariosIam
from app.infrastructure.messaging import (
    manejador_calificaciones,
    manejador_demanda,
    manejador_disponibilidad,
    manejador_notificaciones,
    manejador_prestadores,
)
from app.infrastructure.messaging.consumidor_rabbitmq import ConsumidorRabbitMQ
from app.infrastructure.messaging.manejador_calificaciones import ManejadorCalificaciones
from app.infrastructure.messaging.manejador_demanda import ManejadorDemanda
from app.infrastructure.messaging.manejador_disponibilidad import ManejadorDisponibilidad
from app.infrastructure.messaging.manejador_notificaciones import ManejadorNotificaciones
from app.infrastructure.messaging.manejador_prestadores import ManejadorPrestadores
from app.infrastructure.messaging.publicador_rabbitmq import PublicadorRabbitMQ
from app.infrastructure.messaging.relay_outbox import RelayOutbox
from app.infrastructure.notificaciones.enviador_smtp import EnviadorSmtp
from app.infrastructure.notificaciones.redactor_correos_jinja import RedactorCorreosJinja
from app.infrastructure.observabilidad.configurar_logs import configurar_logs
from app.infrastructure.persistence.consultas.sql_consulta_prestador import SqlConsultaPrestador
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.repositorios.outbox_pendiente import SqlOutboxPendiente
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo
from app.infrastructure.reloj import RelojSistema
from app.infrastructure.tareas.tarea_periodica import TareaPeriodica

logger = logging.getLogger(__name__)


def construir_relay(
    settings: Settings, outbox: SqlOutboxPendiente, publicador: PublicadorRabbitMQ
) -> RelayOutbox:
    reloj = RelojSistema()
    return RelayOutbox(
        publicar=PublicarEventosPendientes(outbox, publicador, reloj, settings.outbox_lote),
        outbox=outbox,
        reloj=reloj,
        lote=settings.outbox_lote,
        intervalo_segundos=settings.outbox_intervalo_segundos,
        espera_maxima_segundos=settings.outbox_espera_maxima_segundos,
        retencion=timedelta(days=settings.outbox_retencion_dias),
    )


def construir_consumidores(
    settings: Settings,
    sesiones: async_sessionmaker[AsyncSession],
    invalidador: InvalidadorCache,
    iam: httpx.AsyncClient,
) -> list[ConsumidorRabbitMQ]:
    reloj = RelojSistema()

    def uow() -> SqlUnidadDeTrabajo:
        return SqlUnidadDeTrabajo(sesiones)

    colas = [
        (
            manejador_prestadores.COLA,
            manejador_prestadores.CLAVES,
            ManejadorPrestadores(
                AplicarPrestadorAprobado(uow, invalidador, reloj),
                AplicarPrestadorSuspendido(uow, invalidador, reloj),
            ),
        ),
        (
            manejador_demanda.COLA,
            manejador_demanda.CLAVES,
            ManejadorDemanda(AplicarEventoReserva(uow)),
        ),
        (
            manejador_calificaciones.COLA,
            manejador_calificaciones.CLAVES,
            ManejadorCalificaciones(AplicarEventoResena(uow)),
        ),
        (
            manejador_disponibilidad.COLA,
            manejador_disponibilidad.CLAVES,
            ManejadorDisponibilidad(AplicarDisponibilidad(uow)),
        ),
        (
            manejador_notificaciones.COLA,
            manejador_notificaciones.CLAVES,
            ManejadorNotificaciones(
                NotificarReserva(
                    uow,
                    SqlConsultaPrestador(sesiones),
                    DirectorioUsuariosIam(iam),
                    RedactorCorreosJinja(),
                    EnviadorSmtp(
                        settings.smtp_host,
                        settings.smtp_port,
                        settings.smtp_remitente,
                        settings.smtp_usuario,
                        settings.smtp_clave,
                        settings.smtp_starttls,
                        settings.smtp_timeout_seconds,
                    ),
                )
            ),
        ),
    ]
    return [
        ConsumidorRabbitMQ(
            settings.rabbitmq_url,
            settings.events_exchange,
            cola,
            claves,
            manejador,
            prefetch=settings.consumidor_prefetch,
            timeout_segundos=settings.rabbitmq_timeout_seconds,
        )
        for cola, claves, manejador in colas
    ]


async def iniciar_consumidores(
    consumidores: list[ConsumidorRabbitMQ], detener: asyncio.Event, espera_maxima: float
) -> None:
    """Si RabbitMQ no está al arrancar, reintenta con espera creciente hasta lograrlo."""
    espera = 1.0
    pendientes = list(consumidores)
    while pendientes and not detener.is_set():
        try:
            await pendientes[0].iniciar()
            pendientes.pop(0)
            espera = 1.0
        except Exception:
            logger.warning("RabbitMQ no disponible para consumir; reintento en %.0f s", espera)
            await pendientes[0].cerrar()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(detener.wait(), timeout=espera)
            espera = min(espera * 2, espera_maxima)


async def correr(settings: Settings) -> None:
    detener = asyncio.Event()
    bucle = asyncio.get_running_loop()
    for senal in (signal.SIGTERM, signal.SIGINT):
        # En Windows no hay manejadores de señales en el bucle: ahí se corta con Ctrl+C.
        with contextlib.suppress(NotImplementedError):
            bucle.add_signal_handler(senal, detener.set)

    engine = build_engine(settings.database_url)
    sesiones = build_session_factory(engine)
    valkey = Valkey.from_url(
        settings.valkey_url,
        socket_timeout=settings.valkey_timeout_seconds,
        socket_connect_timeout=settings.valkey_timeout_seconds,
    )
    publicador = PublicadorRabbitMQ(
        settings.rabbitmq_url, settings.events_exchange, settings.rabbitmq_timeout_seconds
    )
    relay = construir_relay(settings, SqlOutboxPendiente(sesiones), publicador)
    iam = httpx.AsyncClient(base_url=settings.iam_url_interna, timeout=settings.iam_timeout_seconds)
    consumidores = construir_consumidores(settings, sesiones, CacheVersionada(valkey), iam)
    logger.info("Worker iniciado: relay del outbox hacia %s", settings.events_exchange)
    try:
        await asyncio.gather(
            relay.ejecutar(detener),
            iniciar_consumidores(consumidores, detener, settings.outbox_espera_maxima_segundos),
            TareaPeriodica(
                "limpiar-disponibilidad-pasada",
                timedelta(days=1),
                LimpiarDisponibilidadPasada(
                    lambda: SqlUnidadDeTrabajo(sesiones), RelojSistema()
                ).execute,
            ).correr(detener),
        )
    finally:
        for consumidor in consumidores:
            await consumidor.cerrar()
        await publicador.cerrar()
        await iam.aclose()
        await valkey.aclose()
        await engine.dispose()
        logger.info("Worker detenido")


def main() -> None:
    settings = get_settings()
    configurar_logs(f"{settings.service_name}-worker", settings.log_level)
    start_http_server(settings.worker_metrics_port)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(correr(settings))


if __name__ == "__main__":
    main()
