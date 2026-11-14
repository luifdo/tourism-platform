from enum import StrEnum


class PlantillaCorreo(StrEnum):
    """Correos de reservas. Cada uno tiene su HTML y su texto en español e inglés."""

    SOLICITUD = "solicitud"  # al prestador
    MODIFICACION = "modificacion"  # al prestador
    CONFIRMACION = "confirmacion"  # al turista (UC36)
    RECHAZO = "rechazo"  # al turista
    CANCELACION = "cancelacion"  # a la otra parte
