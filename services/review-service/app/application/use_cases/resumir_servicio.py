from uuid import UUID

from app.application.dto.resumen_servicio import ResumenServicio
from app.application.ports.consulta_resenas import ConsultaResenas


class ResumirServicio:
    """Ruta pública: promedio, distribución y aspectos de un servicio. Cuentan las reseñas
    publicadas y en revisión (igual que el promedio de catalog); las ocultas, no."""

    def __init__(self, consulta: ConsultaResenas) -> None:
        self._consulta = consulta

    async def execute(self, servicio_id: UUID) -> ResumenServicio:
        return await self._consulta.resumen(servicio_id)
