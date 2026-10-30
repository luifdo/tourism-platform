"""Valores fijos del dominio. Se exponen como códigos estables; la PWA los traduce."""

from enum import StrEnum


class Categoria(StrEnum):
    PLAYA = "PLAYA"
    NATURALEZA = "NATURALEZA"
    CULTURA = "CULTURA"
    GASTRONOMIA = "GASTRONOMIA"
    AVENTURA = "AVENTURA"
    ALOJAMIENTO = "ALOJAMIENTO"
    TRANSPORTE = "TRANSPORTE"


class UnidadTarifa(StrEnum):
    """A qué corresponde `tarifa_base`: sin ella no se pueden comparar precios."""

    POR_PERSONA = "POR_PERSONA"
    POR_NOCHE = "POR_NOCHE"
    POR_GRUPO = "POR_GRUPO"
    POR_UNIDAD = "POR_UNIDAD"
    POR_HORA = "POR_HORA"
    POR_DIA = "POR_DIA"


class NivelAlerta(StrEnum):
    INFORMATIVA = "INFORMATIVA"
    PREVENTIVA = "PREVENTIVA"
    CRITICA = "CRITICA"


class ResultadoAuditoria(StrEnum):
    """`resultado` de `auditoria.registrada.v1`."""

    EXITO = "EXITO"
    DENEGADO = "DENEGADO"
    ERROR = "ERROR"


class EstadoReserva(StrEnum):
    """Estados de la reserva según booking-service (Plan §6.4)."""

    SOLICITADA = "SOLICITADA"
    CONFIRMADA = "CONFIRMADA"
    RECHAZADA = "RECHAZADA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"

    @property
    def activa(self) -> bool:
        """Una reserva activa ocupa capacidad de carga."""
        return self in (EstadoReserva.SOLICITADA, EstadoReserva.CONFIRMADA)
