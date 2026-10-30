"""Tareas que siguen después de responder (C-50).

`asyncio.create_task` y no `BackgroundTasks` de FastAPI: esas corren en el mismo ciclo de la
petición y retienen la conexión keep-alive. Quien envíe otra petición por esa conexión tardaría
más cuando el correo existe, porque espera al SMTP, y volvería a poder averiguarlo.

La tarea copia el contexto al crearse, así que conserva el `correlation_id` de la petición.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


class TareasSegundoPlano:
    def __init__(self) -> None:
        # El event loop solo guarda referencias débiles: sin este set, una tarea puede
        # desaparecer a medias.
        self._tareas: set[asyncio.Task[None]] = set()

    def lanzar(self, trabajo: Coroutine[Any, Any, None]) -> None:
        tarea = asyncio.create_task(trabajo)
        self._tareas.add(tarea)
        tarea.add_done_callback(self._terminar)

    def _terminar(self, tarea: asyncio.Task[None]) -> None:
        self._tareas.discard(tarea)
        if not tarea.cancelled() and tarea.exception() is not None:
            logger.error("Tarea en segundo plano fallida: %s", type(tarea.exception()).__name__)

    async def esperar(self, timeout_segundos: float | None = None) -> None:
        """Espera las tareas en curso; al apagar el servicio, con un tope."""
        if not self._tareas:
            return
        _, pendientes = await asyncio.wait(self._tareas, timeout=timeout_segundos)
        if pendientes:
            logger.error("Se apagó el servicio con %d tareas sin terminar", len(pendientes))
