from typing import Protocol

from app.application.dto.correo import Correo
from app.application.dto.datos_correo_reserva import DatosCorreoReserva
from app.application.dto.plantilla_correo import PlantillaCorreo


class RedactorCorreos(Protocol):
    def redactar(self, plantilla: PlantillaCorreo, datos: DatosCorreoReserva) -> Correo:
        """En el idioma del destinatario."""
        ...
