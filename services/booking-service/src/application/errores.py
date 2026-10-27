"""Errores de la capa de aplicación (códigos del contrato booking.yaml)."""

from domain.errores import ErrorDominio


class NoEncontrado(ErrorDominio):
    codigo = "NO_ENCONTRADO"


class RolNoPermitido(ErrorDominio):
    codigo = "ROL_NO_PERMITIDO"


class ReservaDuplicada(ErrorDominio):
    codigo = "RESERVA_DUPLICADA"


class DiaExistente(ErrorDominio):
    codigo = "DIA_EXISTENTE"


class VersionDistinta(ErrorDominio):
    codigo = "VERSION_DISTINTA"

    def __init__(self, mensaje: str, version_actual: int):
        super().__init__(mensaje)
        self.version_actual = version_actual


class FaltaIfMatch(ErrorDominio):
    codigo = "FALTA_IF_MATCH"


class PeticionEnProceso(ErrorDominio):
    """Llegó un reintento con la misma Idempotency-Key mientras la primera petición sigue corriendo."""

    codigo = "PETICION_EN_PROCESO"


class IdempotenciaNoDisponible(ErrorDominio):
    """El almacén de idempotencia (Valkey) no responde: es mejor no ejecutar que arriesgar un duplicado."""

    codigo = "IDEMPOTENCIA_NO_DISPONIBLE"
