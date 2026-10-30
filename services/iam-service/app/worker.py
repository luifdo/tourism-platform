"""Worker de iam-service: trabajo en segundo plano, separado de la API (C-31).

Corre con la misma imagen y otro comando (`python -m app.worker`), en su propio Deployment.
Así el consumo de eventos no compite con el ForwardAuth de cada petición protegida, y los
reinicios o el escalado de la API no interrumpen la auditoría.

* Consumidor `iam.auditoria` (`auditoria.registrada` → bitácora, UC33).
* El relay del outbox (`prestador.aprobado`, `prestador.suspendido`) llega en el bloque 4.

Expone sus métricas en `WORKER_METRICS_PORT` (/metrics), que también sirve de sonda de vida.
"""

import asyncio
import contextlib
import logging
import signal

from prometheus_client import start_http_server
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.registrar_evento_auditoria import RegistrarEventoAuditoria
from app.config import Settings, get_settings
from app.infrastructure.messaging import manejador_auditoria
from app.infrastructure.messaging.consumidor_rabbitmq import ConsumidorRabbitMQ
from app.infrastructure.messaging.manejador_auditoria import ManejadorAuditoria
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)


def construir_consumidores(
    settings: Settings, sesiones: async_sessionmaker[AsyncSession]
) -> list[ConsumidorRabbitMQ]:
    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(sesiones)

    colas = [
        (
            manejador_auditoria.COLA,
            manejador_auditoria.CLAVES,
            ManejadorAuditoria(RegistrarEventoAuditoria(uow)),
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
    """Si RabbitMQ no está al arrancar, reintenta con espera creciente hasta lograrlo.

    Una vez conectados, `connect_robust` se encarga de reconectar si el broker se cae.
    """
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
    consumidores = construir_consumidores(settings, build_session_factory(engine))
    logger.info("Worker iniciado")
    try:
        await iniciar_consumidores(consumidores, detener, settings.rabbitmq_espera_maxima_segundos)
        await detener.wait()
    finally:
        for consumidor in consumidores:
            await consumidor.cerrar()
        await engine.dispose()
        logger.info("Worker detenido")


def main() -> None:
    settings = get_settings()
    # Los logs en JSON con correlation_id (formateador de catalog) llegan en el bloque 3.
    logging.basicConfig(
        level=settings.log_level,
        format=f"%(asctime)s %(levelname)s {settings.service_name}-worker %(name)s: %(message)s",
    )
    start_http_server(settings.worker_metrics_port)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(correr(settings))


if __name__ == "__main__":
    main()
