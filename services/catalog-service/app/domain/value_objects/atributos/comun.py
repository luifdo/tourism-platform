"""Validación y conversión a JSON compartidas por los bloques de atributos.

Los bloques se guardan en `atractivo_servicio.atributos` (JSONB): enumeraciones como su
código, textos como `{"es", "en"}`, horas como `"HH:MM"` y valores en pesos como texto
(`"85000.00"`) para no perder decimales.
"""

import re
from collections.abc import Iterable
from datetime import time
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.texto_traducido import TextoTraducido

_IDIOMA = re.compile(r"^[a-z]{2}$")


def en_rango(valor: int | None, campo: str, minimo: int, maximo: int) -> None:
    if valor is not None and not minimo <= valor <= maximo:
        raise DatoInvalido(campo=campo, regla="rango", minimo=minimo, maximo=maximo)


def no_mayor(menor: Any, mayor: Any, campo: str, otro: str) -> None:
    if menor is not None and mayor is not None and menor > mayor:
        raise DatoInvalido(campo=campo, regla="mayor_que", otro=otro)


def sin_repetidos(valores: Iterable[Any], campo: str) -> None:
    lista = list(valores)
    if len(lista) != len(set(lista)):
        raise DatoInvalido(campo=campo, regla="repetido")


def no_vacio(valores: tuple, campo: str) -> None:
    if not valores:
        raise DatoInvalido(campo=campo, regla="obligatorio")


def idiomas(valores: tuple[str, ...], campo: str) -> None:
    """Códigos ISO 639-1 en minúscula (`es`, `en`, `fr`...)."""
    for valor in valores:
        if not _IDIOMA.match(valor):
            raise DatoInvalido(campo=campo, regla="formato")
    sin_repetidos(valores, campo)


def texto_a_json(texto: TextoTraducido | None) -> dict[str, str] | None:
    return texto.a_dict() if texto else None


def texto_desde_json(valor: dict[str, str] | None) -> TextoTraducido | None:
    return TextoTraducido(**valor) if valor else None


def enums_a_json(valores: Iterable[StrEnum]) -> list[str]:
    return [v.value for v in valores]


def enums_desde_json[E: StrEnum](tipo: type[E], valores: Iterable[str] | None) -> tuple[E, ...]:
    return tuple(tipo(v) for v in valores or ())


def hora_a_json(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def pesos_a_json(valor: Decimal | None) -> str | None:
    return str(valor) if valor is not None else None


def sin_nulos(datos: dict[str, Any]) -> dict[str, Any]:
    """El JSON guarda solo lo que el prestador informó."""
    return {k: v for k, v in datos.items() if v is not None and v != []}
