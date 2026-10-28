"""Worker de review-service: trabajo en segundo plano, separado de la API.

Corre con la misma imagen y otro comando (`python -m app.worker`), en su propio Deployment.
La API no depende de él: si se cae, las reseñas se siguen escribiendo y sus eventos esperan
en el outbox (ESC-01).

* Relay del outbox → `turismo.eventos` (`resena.publicada`, `resena.ocultada`) y limpieza
  diaria del outbox ya publicado.
* Consumidores de `reserva.finalizada` y `servicio.publicado` (paso 5).
* Limpieza diaria de la idempotencia vencida y de `evento_procesado` viejo.

Expone sus métricas en `WORKER_METRICS_PORT` (/metrics), que también sirve de sonda de vida.
"""

import asyncio
import contextlib
import logging
import signal
from datetime import timedelta

from prometheus_client import start_http_server
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.limpiar_registros_vencidos import LimpiarRegistrosVencidos
from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.config import Settings, get_settings
from app.infrastructure.messaging.consumidor_rabbitmq import ConsumidorRabbitMQ, Manejador
from app.infrastructure.messaging.publicador_rabbitmq import PublicadorRabbitMQ
from app.infrastructure.messaging.relay_outbox import RelayOutbox
from app.infrastructure.observabilidad.configurar_logs import configurar_logs
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.repositorios.outbox_pendiente import SqlOutboxPendiente
from app.infrastructure.persistence.repositorios.registros_vencidos import SqlRegistrosVencidos
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
    settings: Settings, sesiones: async_sessionmaker[AsyncSession]
) -> list[ConsumidorRabbitMQ]:
    # Los consumidores de review.elegibilidad y review.servicios llegan en el paso 5.
    colas: list[tuple[str, tuple[str, ...], Manejador]] = []
    return [
        ConsumidorRabbitMQ(
            url=settings.rabbitmq_url,
            exchange=settings.events_exchange,
            cola=cola,
            claves=claves,
            manejar=manejador,
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
    publicador = PublicadorRabbitMQ(
        settings.rabbitmq_url, settings.events_exchange, settings.rabbitmq_timeout_seconds
    )
    relay = construir_relay(settings, SqlOutboxPendiente(sesiones), publicador)
    consumidores = construir_consumidores(settings, sesiones)
    limpieza = LimpiarRegistrosVencidos(
        SqlRegistrosVencidos(sesiones),
        RelojSistema(),
        timedelta(days=settings.evento_procesado_retencion_dias),
    )
    logger.info("Worker iniciado: relay del outbox hacia %s", settings.events_exchange)
    try:
        await asyncio.gather(
            relay.ejecutar(detener),
            iniciar_consumidores(consumidores, detener, settings.outbox_espera_maxima_segundos),
            TareaPeriodica(
                "limpiar-registros-vencidos", timedelta(days=1), limpieza.execute
            ).correr(detener),
        )
    finally:
        for consumidor in consumidores:
            await consumidor.cerrar()
        await publicador.cerrar()
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
