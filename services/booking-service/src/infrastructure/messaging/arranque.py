"""Arranque y parada de la mensajería en modo postgres (relay del outbox).

Todo corre como tarea de fondo: si RabbitMQ no está al arrancar, la app sube igual (las
peticiones siguen funcionando y los eventos esperan en el outbox) y la tarea reintenta la
conexión cada pocos segundos.
"""

import asyncio
import logging

from aio_pika.abc import AbstractRobustConnection
from sqlalchemy.ext.asyncio import AsyncEngine

from config import Configuracion
from infrastructure.messaging.rabbitmq import PublicadorRabbitMQ, conectar
from infrastructure.messaging.relay import RelayOutbox

log = logging.getLogger("booking.mensajeria")
ESPERA_RECONEXION_S = 5.0


class Mensajeria:
    def __init__(self, config: Configuracion, motor: AsyncEngine):
        self._config = config
        self._motor = motor
        self._parar = asyncio.Event()
        self._tarea: asyncio.Task | None = None
        self._conexion: AbstractRobustConnection | None = None

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._correr(), name="relay-outbox")

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
        publicador = PublicadorRabbitMQ(self._conexion, self._config.events_exchange)
        relay = RelayOutbox(self._motor, publicador, self._config.relay_lote)
        await relay.correr(self._parar, self._config.relay_espera_s)

    async def detener(self) -> None:
        """Termina la vuelta en curso (no deja un lote a medias) y cierra la conexión."""
        self._parar.set()
        if self._tarea:
            await self._tarea
        if self._conexion:
            await self._conexion.close()
