"""Punto de entrada de los CronJobs de booking (Guía §6.4).

    python -m cron expirar-solicitudes    # SOLICITADA vencidas → RECHAZADA, libera cupos
    python -m cron finalizar-reservas     # CONFIRMADA de días pasados → FINALIZADA

Usa la misma imagen que la API (en el contenedor, PYTHONPATH=/srv/src). Cada ejecución abre
el motor, procesa todos los lotes y termina: el código de salida le dice a Kubernetes si el Job
salió bien. Los eventos quedan en evento_outbox en la misma transacción del lote; los publica el
relay que corre en los pods de la API, así que el CronJob no necesita RabbitMQ.
"""

import argparse
import asyncio
import logging
import sys
from typing import Any

from application.base import Contexto
from application.tareas import ExpirarSolicitudes, FinalizarReservas
from config import Configuracion
from infrastructure.observabilidad.correlacion import fijar_correlation_id
from infrastructure.observabilidad.logs import configurar_logs
from infrastructure.persistence.db import crear_motor, fabrica_sesiones
from infrastructure.persistence.postgres import fabrica_postgres
from infrastructure.reloj import RelojSistema

# El nombre de la tarea es el del CronJob en k8s/base/.
TAREAS = {"expirar-solicitudes": ExpirarSolicitudes, "finalizar-reservas": FinalizarReservas}

log = logging.getLogger("booking.cron")


async def ejecutar(nombre: str, config: Configuracion, reloj: Any = None) -> int:
    """Corre la tarea contra booking_db y devuelve cuántas reservas cambió."""
    motor = crear_motor(config)
    try:
        ctx = Contexto(fabrica_postgres(fabrica_sesiones(motor)), reloj or RelojSistema(), config.plazo_respuesta_horas)
        return await TAREAS[nombre](ctx)()
    finally:
        await motor.dispose()


def main(argv: list[str] | None = None, config: Configuracion | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cron", description="Tareas programadas de booking-service.")
    parser.add_argument("tarea", choices=sorted(TAREAS))
    nombre = parser.parse_args(argv).tarea

    config = config or Configuracion()
    configurar_logs(config.service_name, config.log_level)
    fijar_correlation_id(f"cron-{nombre}")  # cada línea de log del Job se puede buscar en Loki
    if config.modo_persistencia != "postgres":
        # En memoria cada proceso tiene sus propios datos: el CronJob no vería las reservas de la API.
        log.error("Los CronJobs necesitan MODO_PERSISTENCIA=postgres (en memoria use las rutas /dev).")
        return 2
    try:
        total = asyncio.run(ejecutar(nombre, config))
    except Exception:
        log.exception("Falló la tarea %s", nombre)
        return 1
    log.info("Tarea %s terminada: %d reservas actualizadas", nombre, total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
