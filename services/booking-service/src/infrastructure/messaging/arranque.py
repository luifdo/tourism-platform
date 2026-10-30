"""Arranque y parada de la mensajería en modo postgres: relay del outbox y consumidor de servicios.

Todo corre como tarea de fondo: si RabbitMQ no está al arrancar, la app sube igual (las
peticiones siguen funcionando y los eventos esperan en el outbox) y la tarea reintenta la
conexión cada pocos segundos. Al conectar, lo primero es declarar la cola `booking.servicios`
(Guía §5): RabbitMQ descarta lo que catalog publique mientras no haya una cola enlazada.
"""

import asyncio
import logging

from aio_pika.abc import AbstractRobustConnection
from sqlalchemy.ext.asyncio import AsyncEngine

from application.base import Contexto
from config import Configuracion
from infrastructure.messaging.consumidor import ConsumidorRabbitMQ, manejador_servicios
from infrastructure.messaging.rabbitmq import CLAVE_SERVICIOS, COLA_SERVICIOS, PublicadorRabbitMQ, conectar
from infrastructure.messaging.relay import RelayOutbox

log = logging.getLogger("booking.mensajeria")
ESPERA_RECONEXION_S = 5.0


class Mensajeria:
    def __init__(self, config: Configuracion, motor: AsyncEngine, ctx: Contexto):
        self._config = config
        self._motor = motor
        self._ctx = ctx
        self._parar = asyncio.Event()
        self._tarea: asyncio.Task | None = None
        self._conexion: AbstractRobustConnection | None = None
        self._consumidor: ConsumidorRabbitMQ | None = None

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._correr(), name="mensajeria")

    async def _conectar(self) -> AbstractRobustConnection | None:
        while not self._parar.is_set():
            try:
                return await conectar(self._config.rabbitmq_url)
            except Exception as error:
                log.warning("RabbitMQ no responde (%s); reintento en %.0f s", error, ESPERA_RECONEXION_S)
                try:
                    await asyncio.wait_for(self._parar.wait(), ESPERA_RECONEXION_S)
                except TimeoutError:
                    pass
        return None

    async def _correr(self) -> None:
        self._conexion = await self._conectar()
        if self._conexion is None:
            return
        self._consumidor = ConsumidorRabbitMQ(
            self._conexion, self._config.events_exchange, COLA_SERVICIOS, [CLAVE_SERVICIOS],
            manejador_servicios(self._ctx),
        )
        try:
            await self._consumidor.iniciar()
        except Exception:  # p. ej. PRECONDITION_FAILED si otro servicio declaró distinto: el relay sigue
            log.exception("No se pudo iniciar el consumidor de %s", COLA_SERVICIOS)
        publicador = PublicadorRabbitMQ(self._conexion, self._config.events_exchange)
        relay = RelayOutbox(self._motor, publicador, self._config.relay_lote)
        await relay.correr(self._parar, self._config.relay_espera_s)

    async def detener(self) -> None:
        """Deja de consumir, termina la vuelta del relay en curso y cierra la conexión."""
        self._parar.set()
        if self._consumidor:
            await self._consumidor.detener()
        if self._tarea:
            await self._tarea
        if self._conexion:
            await self._conexion.close()
