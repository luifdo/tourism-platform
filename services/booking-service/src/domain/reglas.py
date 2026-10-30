"""Reglas de tiempo de la reserva (Guía §4.1 y §4.3).

Todas las fechas se interpretan en America/Bogota; la unidad de reserva es el día.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from domain.errores import Validacion

ZONA = ZoneInfo("America/Bogota")
PLAZO_RESPUESTA_HORAS = 48


def hoy_local(ahora: datetime) -> date:
    return ahora.astimezone(ZONA).date()


def inicio_del_dia(fecha: date) -> datetime:
    return datetime.combine(fecha, time.min, tzinfo=ZONA)


def validar_fecha_solicitud(fecha_reserva: date, ahora: datetime) -> None:
    """Solo se aceptan solicitudes a partir de mañana."""
    if fecha_reserva <= hoy_local(ahora):
        raise Validacion("La fecha de la reserva debe ser a partir de mañana.")


def calcular_expira_en(
    fecha_reserva: date, ahora: datetime, plazo_horas: int = PLAZO_RESPUESTA_HORAS
) -> datetime:
    """Plazo de respuesta del prestador: mín(ahora + plazo, inicio del día de la reserva)."""
    return min(ahora + timedelta(hours=plazo_horas), inicio_del_dia(fecha_reserva))


def turista_puede_cancelar_confirmada(fecha_reserva: date, ahora: datetime) -> bool:
    """El turista cancela una reserva confirmada hasta las 23:59 del día anterior."""
    return hoy_local(ahora) < fecha_reserva
