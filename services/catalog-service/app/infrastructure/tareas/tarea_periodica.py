"""Tarea de mantenimiento que el worker corre cada cierto tiempo (p. ej. una vez al día).

Corre al arrancar y luego cada `cada`. Si falla, se registra en el log y se reintenta en la
siguiente vuelta: una limpieza que no corrió hoy no afecta a nadie. Con varias réplicas del
worker puede correr en más de una; por eso las tareas deben poder repetirse sin daño.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)


class TareaPeriodica:
    def __init__(
        self, nombre: str, cada: timedelta, ejecutar: Callable[[], Awaitable[Any]]
    ) -> None:
        self._nombre = nombre
        self._cada = cada
        self._ejecutar = ejecutar

    async def correr(self, detener: asyncio.Event) -> None:
        while not detener.is_set():
            try:
                await self._ejecutar()
            except Exception:
                logger.exception(
                    "Falló la tarea %s; se reintenta en la próxima vuelta", self._nombre
                )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(detener.wait(), timeout=self._cada.total_seconds())
