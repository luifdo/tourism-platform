import logging

from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.ports.reloj import Reloj

logger = logging.getLogger(__name__)


class LimpiarDisponibilidadPasada:
    """Borra los días ya pasados de `disponibilidad_proyeccion`: solo sirven para buscar
    fechas futuras. Las reservas (`reserva_proyeccion`) no se borran: son la analítica."""

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(self) -> int:
        async with self._uow() as uow:
            borrados = await uow.disponibilidad.borrar_anteriores(self._reloj.hoy())
            await uow.confirmar()
        if borrados:
            logger.info("Disponibilidad: %d días pasados borrados", borrados)
        return borrados
