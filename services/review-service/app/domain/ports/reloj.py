from datetime import date, datetime
from typing import Protocol


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """Instante actual en UTC (con zona horaria)."""
        ...

    def hoy(self) -> date:
        """Fecha de negocio actual en America/Bogota."""
        ...
