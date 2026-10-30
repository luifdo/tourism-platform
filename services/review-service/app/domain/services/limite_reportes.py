import math
from collections.abc import Iterable
from datetime import datetime, timedelta

from app.domain.errors import DemasiadosReportes

LIMITE_POR_HORA = 10
VENTANA = timedelta(hours=1)


class LimiteReportes:
    """Como máximo 10 reportes por usuario en la última hora (UC39), contra el abuso."""

    def exigir(self, reportes_recientes: Iterable[datetime], ahora: datetime) -> None:
        """`reportes_recientes`: cuándo reportó el usuario en la última hora.

        Si ya llegó al límite, `Retry-After` es lo que falta para que venza el más antiguo.
        """
        dentro = sorted(r for r in reportes_recientes if r > ahora - VENTANA)
        if len(dentro) < LIMITE_POR_HORA:
            return
        libera = dentro[-LIMITE_POR_HORA] + VENTANA
        espera = math.ceil((libera - ahora).total_seconds())
        raise DemasiadosReportes(retry_after=max(espera, 1), limite=LIMITE_POR_HORA)
