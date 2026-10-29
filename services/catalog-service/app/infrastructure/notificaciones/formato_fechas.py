"""Fechas legibles en español e inglés para los correos, sin depender del locale del sistema
(en los contenedores y en Windows no siempre está instalado)."""

from datetime import date, datetime

from app.domain.value_objects.idioma import Idioma
from app.infrastructure.reloj import ZONA_NEGOCIO

_DIAS = {
    Idioma.ES: ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    Idioma.EN: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
_MESES = {
    Idioma.ES: [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ],
    Idioma.EN: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
}  # fmt: skip


def fecha_larga(dia: date, idioma: Idioma) -> str:
    """«jueves 5 de noviembre de 2026» / «Thursday, November 5, 2026»."""
    nombre_dia, mes = _DIAS[idioma][dia.weekday()], _MESES[idioma][dia.month - 1]
    if idioma is Idioma.EN:
        return f"{nombre_dia}, {mes} {dia.day}, {dia.year}"
    return f"{nombre_dia} {dia.day} de {mes} de {dia.year}"


def fecha_y_hora(momento: datetime, idioma: Idioma) -> str:
    """En la hora de Santa Marta: «jueves 5 de noviembre de 2026, 14:30»."""
    local = momento.astimezone(ZONA_NEGOCIO)
    return f"{fecha_larga(local.date(), idioma)}, {local:%H:%M}"
