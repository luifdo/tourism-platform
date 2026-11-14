import logging
from datetime import timedelta

from app.application.ports.registros_vencidos import RegistrosVencidos
from app.domain.ports.reloj import Reloj

logger = logging.getLogger(__name__)


class LimpiarRegistrosVencidos:
    """Limpieza diaria del worker: borra lo que ya no protege nada.

    * Idempotencia vencida: una clave vencida no evita ningún reenvío (`reservar` igual la
      retoma); borrarla solo libera espacio.
    * `evento_procesado` de más de `retencion`: los duplicados llegan mucho antes, y los
      consumidores de review ya son idempotentes por sí mismos (la visita más reciente, la
      versión mayor del dueño).

    Nunca toca reseñas, reportes ni proyecciones. El outbox publicado lo limpia el relay.
    """

    def __init__(self, registros: RegistrosVencidos, reloj: Reloj, retencion: timedelta) -> None:
        self._registros = registros
        self._reloj = reloj
        self._retencion = retencion

    async def execute(self) -> tuple[int, int]:
        claves = await self._registros.borrar_idempotencia_vencida()
        eventos = await self._registros.borrar_eventos_procesados(
            self._reloj.ahora() - self._retencion
        )
        if claves or eventos:
            logger.info(
                "Limpieza: %d claves de idempotencia vencidas y %d eventos procesados viejos",
                claves,
                eventos,
            )
        return claves, eventos
