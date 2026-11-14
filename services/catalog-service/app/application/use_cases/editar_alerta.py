from datetime import datetime
from uuid import UUID

from app.application.dto.alerta_editable import AlertaEditable
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.escritura_alerta import EscrituraAlerta
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad
from app.domain.value_objects.texto_traducido import TextoTraducido


class EditarAlerta:
    """UC26: corregir una alerta vigente o cambiar su vigencia, con la versión que se leyó.

    Por ejemplo, "el sendero sigue cerrado una semana más". El destino no cambia.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, escritura: EscrituraAlerta, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        alerta_id: UUID,
        version_esperada: int,
        nivel: NivelAlerta,
        mensaje: TextoTraducido,
        fecha_expiracion: datetime,
    ) -> AlertaEditable:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            alerta = await uow.alertas.obtener(alerta_id)
            if alerta is None:
                raise NoEncontrado(recurso="alerta", id=str(alerta_id))
            alerta.editar(version_esperada, nivel, mensaje, fecha_expiracion, ahora)
            editable = await self._escritura.guardar_y_auditar(
                uow,
                alerta,
                await self._escritura.zona_de(uow, alerta),
                identidad,
                "ALERTA_EDITADA",
                ahora,
            )
            await uow.confirmar()
        return editable
