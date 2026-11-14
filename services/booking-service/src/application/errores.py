"""Errores de la capa de aplicación (códigos del contrato booking.yaml)."""

from domain.disponibilidad import DisponibilidadCupo
from domain.errores import ErrorDominio
from domain.reserva import Reserva


class NoEncontrado(ErrorDominio):
    codigo = "NO_ENCONTRADO"


class RolNoPermitido(ErrorDominio):
    codigo = "ROL_NO_PERMITIDO"


class ReservaDuplicada(ErrorDominio):
    codigo = "RESERVA_DUPLICADA"


class DiaExistente(ErrorDominio):
    codigo = "DIA_EXISTENTE"


class VersionDistinta(ErrorDominio):
    """El registro cambió en el servidor después de que el usuario lo leyó (If-Match viejo).

    Lleva el registro tal como está ahora para que la PWA muestre el conflicto sin otro GET.
    """

    codigo = "VERSION_DISTINTA"

    def __init__(self, mensaje: str, actual: Reserva | DisponibilidadCupo):
        super().__init__(mensaje)
        self.actual = actual

    @property
    def version_actual(self) -> int:
        return self.actual.version


class FaltaIfMatch(ErrorDominio):
    codigo = "FALTA_IF_MATCH"


class PeticionEnProceso(ErrorDominio):
    """Llegó un reintento con la misma Idempotency-Key mientras la primera petición sigue corriendo."""

    codigo = "PETICION_EN_PROCESO"


class IdempotenciaNoDisponible(ErrorDominio):
    """El almacén de idempotencia (Valkey) no responde: es mejor no ejecutar que arriesgar un duplicado."""

    codigo = "IDEMPOTENCIA_NO_DISPONIBLE"
