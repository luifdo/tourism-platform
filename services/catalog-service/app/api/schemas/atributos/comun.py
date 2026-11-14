"""Tipos y conversiones compartidas por los esquemas de atributos."""

from datetime import time
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido

# Horas como "14:00", igual que se guardan y se muestran.
Hora = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["14:00"])]
Pesos = Annotated[float, Field(ge=0)]
Idiomas = Annotated[list[str], Field(max_length=20, examples=[["es", "en"]])]


def texto(datos: TextoTraducidoDatos | None) -> TextoTraducido | None:
    return datos.a_dominio() if datos else None


def texto_datos(valor: TextoTraducido | None) -> TextoTraducidoDatos | None:
    return TextoTraducidoDatos.desde(valor) if valor else None


def hora(valor: str) -> time:
    return time.fromisoformat(valor)


def hora_texto(valor: time) -> str:
    return valor.strftime("%H:%M")


def tarifa(valor: float | None) -> Tarifa | None:
    return Tarifa(Decimal(str(valor))) if valor is not None else None


def pesos(valor: Tarifa | None) -> float | None:
    return float(valor.valor) if valor else None
