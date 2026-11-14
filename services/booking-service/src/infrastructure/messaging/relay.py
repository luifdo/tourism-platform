"""Relay del outbox: lleva los eventos pendientes de `evento_outbox` a RabbitMQ.

Corre como tarea de fondo en cada réplica. Cada vuelta, en una transacción:
1. toma hasta `lote` pendientes, en el orden en que se produjeron, con FOR UPDATE SKIP LOCKED:
   dos réplicas nunca toman el mismo evento, y ninguna espera a la otra;
2. los publica uno a uno, esperando la confirmación de RabbitMQ;
3. marca `publicado_en` en los confirmados. Si uno falla, suma un intento, guarda el error y
   corta el lote: los siguientes esperan, para no adelantarse a él.

Entrega "al menos una vez": si el pod se cae después de publicar y antes del COMMIT, el evento
sale otra vez en la próxima vuelta. Por eso viaja el `event_id`: los consumidores lo descartan.
"""

import asyncio
import logging
from typing import Any, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from infrastructure.persistence.tablas import evento_outbox

log = logging.getLogger("booking.relay")
INTENTOS_PARA_ALERTA = 3  # Guía §6.5: tras 3 intentos fallidos queda un registro de error
ERROR_MAX = 500


class PublicadorSobres(Protocol):
    async def publicar(self, sobres: list[dict[str, Any]]) -> None: ...


class RelayOutbox:
    def __init__(self, motor: AsyncEngine, publicador: PublicadorSobres, lote: int = 100):
        self._motor = motor
        self._publicador = publicador
        self._lote = lote

    async def una_vuelta(self) -> int:
        """Publica un lote; devuelve cuántos eventos quedaron publicados."""
        o = evento_outbox.c
        async with self._motor.begin() as con:
            pendientes = (await con.execute(
                select(o.id, o.tipo, o.sobre, o.intentos)
                .where(o.publicado_en.is_(None))
                .order_by(o.creado_en)
                .limit(self._lote)
                .with_for_update(skip_locked=True)
            )).all()
            publicados = []
            for fila in pendientes:
                try:
                    await self._publicador.publicar([fila.sobre])
                except Exception as error:  # broker caído, conexión cortada, nack...
                    await con.execute(
                        update(evento_outbox).where(o.id == fila.id)
                        .values(intentos=o.intentos + 1, ultimo_error=f"{type(error).__name__}: {error}"[:ERROR_MAX])
                    )
                    nivel = logging.ERROR if fila.intentos + 1 >= INTENTOS_PARA_ALERTA else logging.WARNING
                    log.log(nivel, "No se pudo publicar %s %s (intento %d): %s", fila.tipo, fila.id,
                            fila.intentos + 1, error, extra={"payload": fila.sobre.get("payload")})
                    break
                publicados.append(fila.id)
            if publicados:
                await con.execute(update(evento_outbox).where(o.id.in_(publicados)).values(publicado_en=func.now()))
        return len(publicados)

    async def correr(self, parar: asyncio.Event, espera_s: float = 1.0) -> None:
        """Vueltas sin pausa mientras haya lotes llenos; si no, espera `espera_s` (o más tras un error)."""
        espera_error = espera_s
        while not parar.is_set():
            try:
                publicados = await self.una_vuelta()
                espera_error = espera_s
                if publicados == self._lote:
                    continue
                pausa = espera_s
            except Exception:  # p. ej. la base no responde: se reintenta, el relay no muere
                log.exception("Falló una vuelta del relay del outbox")
                espera_error = min(espera_error * 2, 30.0)
                pausa = espera_error
            try:
                await asyncio.wait_for(parar.wait(), pausa)
            except TimeoutError:
                pass
