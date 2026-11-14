from uuid import UUID

from app.application.dto.alerta_editable import AlertaEditable
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.escritura_alerta import EscrituraAlerta
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad


class RetirarAlerta:
    """UC26: la alerta deja de mostrarse. No se borra (queda en el panel como retirada).

    Retirar una ya retirada no cambia nada ni se audita, así un reenvío no genera ruido.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, escritura: EscrituraAlerta, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._reloj = reloj

    async def execute(self, identidad: Identidad, alerta_id: UUID) -> AlertaEditable:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            alerta = await uow.alertas.obtener(alerta_id)
            if alerta is None:
                raise NoEncontrado(recurso="alerta", id=str(alerta_id))
            zona_codigo = await self._escritura.zona_de(uow, alerta)
            if not alerta.desactivar():
                return AlertaEditable(alerta, zona_codigo)
            editable = await self._escritura.guardar_y_auditar(
                uow, alerta, zona_codigo, identidad, "ALERTA_RETIRADA", ahora
            )
            await uow.confirmar()
        return editable
