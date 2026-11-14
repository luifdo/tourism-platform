import enum


class Rol(enum.Enum):
    TURISTA = "Turista"
    PRESTADOR = "Prestador"
    ENTIDAD = "Entidad"
    ADMIN = "Admin"


class Idioma(enum.Enum):
    """Idioma de los correos del usuario (RF-10, C-06)."""

    ES = "es"
    EN = "en"


class TipoDocumento(enum.Enum):
    RNT = "RNT"
    RUT = "RUT"


class EstadoDocumento(enum.Enum):
    PENDIENTE = "Pendiente"
    APROBADO = "Aprobado"
    RECHAZADO = "Rechazado"


class ResultadoAuditoria(enum.Enum):
    EXITO = "Exito"
    DENEGADO = "Denegado"
    ERROR = "Error"
