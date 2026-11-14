from datetime import date
from typing import Protocol

from app.application.dto.cargas_capacidad import CargasCapacidad


class ConsultaCapacidad(Protocol):
    async def cargas(self, fecha: date, zona: str | None = None) -> CargasCapacidad:
        """Cargas de las zonas activas (o solo de `zona`) ese día. Una zona activa sin
        servicios aparece sin cargas; una que no existe o está inactiva, no aparece."""
        ...
