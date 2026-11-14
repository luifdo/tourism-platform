"""Idempotencia de formularios en PostgreSQL (Plan §6.8; implementa AlmacenIdempotencia).

Review no usa Valkey: las reseñas no necesitan esa latencia y así el servicio depende de una
pieza menos.

* Cada llamada usa su propia transacción corta, fuera de la unidad de trabajo: la reserva
  debe verse en otras réplicas antes de que la operación termine.
* Mientras la operación corre, la clave vence a los 60 s (si el pod muere a mitad, el
  reintento puede ejecutarse pasado ese tiempo). Con éxito, la respuesta se guarda 48 h
  (`Idempotency-Key` del contrato).
* Los tiempos los pone `now()` de la base, el mismo reloj para todas las réplicas.
* Las filas vencidas no estorban (`reservar` las retoma); el worker las borra cada día.
"""

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto.respuesta_guardada import RespuestaGuardada
from app.infrastructure.persistence.modelos.idempotencia import IdempotenciaModelo

EN_PROCESO = text("now() + interval '60 seconds'")
CON_RESPUESTA = text("now() + interval '48 hours'")
AHORA = text("now()")


class IdempotenciaPostgres:
    def __init__(self, sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesiones = sesiones

    async def reservar(self, clave: str) -> RespuestaGuardada | bool:
        m = IdempotenciaModelo
        async with self._sesiones.begin() as session:
            nueva = await session.scalar(
                insert(m)
                .values(clave=clave, expira_en=EN_PROCESO)
                .on_conflict_do_nothing()
                .returning(m.clave)
            )
            if nueva is not None:
                return True
            # Vencida: el intento anterior murió a mitad o su respuesta ya cumplió 48 h.
            retomada = await session.scalar(
                update(m)
                .where(m.clave == clave, m.expira_en < AHORA)
                .values(estado_http=None, cuerpo=None, cabeceras=None, expira_en=EN_PROCESO)
                .returning(m.clave)
            )
            if retomada is not None:
                return True
            fila = await session.scalar(select(m).where(m.clave == clave))
        if fila is None or fila.estado_http is None or fila.cuerpo is None:
            return False  # el otro intento sigue (o se acaba de liberar): que el cliente reintente
        return RespuestaGuardada(fila.estado_http, fila.cuerpo, fila.cabeceras or {})

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None:
        m = IdempotenciaModelo
        async with self._sesiones.begin() as session:
            await session.execute(
                update(m)
                .where(m.clave == clave)
                .values(
                    estado_http=respuesta.estado,
                    cuerpo=respuesta.cuerpo,
                    cabeceras=respuesta.cabeceras,
                    expira_en=CON_RESPUESTA,
                )
            )

    async def liberar(self, clave: str) -> None:
        """La operación falló: un reintento con la misma clave debe poder ejecutarse."""
        async with self._sesiones.begin() as session:
            await session.execute(
                delete(IdempotenciaModelo).where(IdempotenciaModelo.clave == clave)
            )
