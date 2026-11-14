"""Bucle del relay del outbox. Corre en el worker, separado de la API.

* Cada `intervalo` publica un lote; si el lote salió lleno, sigue de inmediato.
* Si RabbitMQ o PostgreSQL fallan, espera el doble cada vez, hasta `espera_maxima`; al
  primer lote bueno vuelve al intervalo normal.
* Una vez al día borra los eventos ya publicados con más de `retencion` de antigüedad.
"""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta

from app.application.ports.outbox_pendiente import OutboxPendiente
from app.application.use_cases.publicar_eventos_pendientes import PublicarEventosPendientes
from app.domain.ports.reloj import Reloj
from app.infrastructure.observabilidad import metricas_outbox as metricas

logger = logging.getLogger(__name__)

LIMPIEZA_CADA = timedelta(days=1)


class RelayOutbox:
    def __init__(
        self,
        publicar: PublicarEventosPendientes,
        outbox: OutboxPendiente,
        reloj: Reloj,
        lote: int,
        intervalo_segundos: float,
        espera_maxima_segundos: float,
        retencion: timedelta,
    ) -> None:
        self._publicar = publicar
        self._outbox = outbox
        self._reloj = reloj
        self._lote = lote
        self._intervalo = intervalo_segundos
        self._espera_maxima = espera_maxima_segundos
        self._retencion = retencion
        self._ultima_limpieza: datetime | None = None

    async def ejecutar(self, detener: asyncio.Event) -> None:
        espera = self._intervalo
        while not detener.is_set():
            espera = await self.una_vuelta(espera)
            if espera > 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(detener.wait(), timeout=espera)

    async def una_vuelta(self, espera_anterior: float) -> float:
        """Publica un lote y devuelve cuánto esperar antes del siguiente."""
        try:
            resultado = await self._publicar.execute()
        except Exception:
            logger.exception("El relay del outbox no pudo procesar el lote")
            metricas.FALLOS_PUBLICACION.inc()
            return self._siguiente_espera(espera_anterior)
        for event_type in resultado.publicados:
            metricas.EVENTOS_PUBLICADOS.labels(event_type=event_type).inc()
        await self._actualizar_estado()
        await self._limpiar_si_toca()
        if resultado.fallo:
            metricas.FALLOS_PUBLICACION.inc()
            return self._siguiente_espera(espera_anterior)
        return 0 if len(resultado.publicados) >= self._lote else self._intervalo

    def _siguiente_espera(self, anterior: float) -> float:
        return min(max(anterior, self._intervalo) * 2, self._espera_maxima)

    async def _actualizar_estado(self) -> None:
        try:
            estado = await self._outbox.estado()
        except Exception:
            logger.warning("No se pudo leer el estado del outbox", exc_info=True)
            return
        metricas.PENDIENTES.set(estado.pendientes)
        antiguedad = (
            (self._reloj.ahora() - estado.mas_antiguo).total_seconds() if estado.mas_antiguo else 0
        )
        metricas.ANTIGUEDAD.set(max(antiguedad, 0))

    async def _limpiar_si_toca(self) -> None:
        ahora = self._reloj.ahora()
        if self._ultima_limpieza and ahora - self._ultima_limpieza < LIMPIEZA_CADA:
            return
        self._ultima_limpieza = ahora
        try:
            borrados = await self._outbox.limpiar_publicados(ahora - self._retencion)
        except Exception:
            logger.warning("No se pudo limpiar el outbox", exc_info=True)
            return
        if borrados:
            logger.info("Outbox: %d eventos publicados borrados", borrados)
