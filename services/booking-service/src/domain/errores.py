"""Errores de dominio. Cada uno lleva el código del contrato (booking.yaml)."""


class ErrorDominio(Exception):
    codigo = "ERROR_DOMINIO"

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class Validacion(ErrorDominio):
    codigo = "VALIDACION"


class TransicionInvalida(ErrorDominio):
    codigo = "TRANSICION_INVALIDA"


class PlazoVencido(ErrorDominio):
    codigo = "PLAZO_VENCIDO"


class FueraDePlazo(ErrorDominio):
    codigo = "FUERA_DE_PLAZO"


class CuposInsuficientes(ErrorDominio):
    codigo = "CUPOS_INSUFICIENTES"


class CuposComprometidos(ErrorDominio):
    codigo = "CUPOS_COMPROMETIDOS"


class SuperaAforo(ErrorDominio):
    codigo = "SUPERA_AFORO"


class NoDisponible(ErrorDominio):
    """El día no está abierto o el servicio está inactivo."""

    codigo = "DIA_NO_DISPONIBLE"
