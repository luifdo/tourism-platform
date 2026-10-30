from datetime import date
from typing import Protocol
from uuid import UUID

from app.application.dto.intenciones_zona_dia import IntencionesZonaDia
from app.application.dto.rango_fechas import RangoFechas


class ContadorIntenciones(Protocol):
    async def sumar(self, servicio_id: UUID, fecha: date) -> bool:
        """Suma una intención si el servicio existe y está activo; si no, devuelve False."""
        ...

    async def por_zona(self, rango: RangoFechas, zona: str | None) -> list[IntencionesZonaDia]:
        """Conteos por zona (la zona actual de cada servicio) y día; sin zona, no salen."""
        ...
