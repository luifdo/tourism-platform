from app.application.dto.estado_alerta import EstadoAlerta
from app.application.dto.pagina_alertas_entidad import PaginaAlertasEntidad
from app.application.ports.consulta_alertas import ConsultaAlertas
from app.domain.errors import DatoInvalido
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class ListarAlertasEntidad:
    """Panel de la Entidad: sus alertas vigentes, vencidas y retiradas, para administrarlas."""

    def __init__(self, consulta: ConsultaAlertas, reloj: Reloj) -> None:
        self._consulta = consulta
        self._reloj = reloj

    async def execute(
        self, identidad: Identidad, estado: EstadoAlerta | None, pagina: int, tamano: int
    ) -> PaginaAlertasEntidad:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        if pagina < 1:
            raise DatoInvalido(campo="pagina", regla="minimo", minimo=1)
        return await self._consulta.de_entidad(self._reloj.ahora(), estado, pagina, tamano)
