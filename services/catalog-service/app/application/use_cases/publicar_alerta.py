from datetime import datetime
from uuid import UUID

from app.application.dto.alerta_editable import AlertaEditable
from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.escritura_alerta import EscrituraAlerta
from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.errors import DatoInvalido, NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad
from app.domain.value_objects.texto_traducido import TextoTraducido


class PublicarAlerta:
    """UC26: la Entidad publica un aviso oficial sobre un servicio o una zona completa.

    El destino debe existir y estar activo. No depende de la saturación: también hay
    alertas por clima, cierres o seguridad.
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
        nivel: NivelAlerta,
        mensaje: TextoTraducido,
        fecha_expiracion: datetime,
        servicio_id: UUID | None,
        zona: CodigoZona | None,
    ) -> AlertaEditable:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        if (servicio_id is None) == (zona is None):
            raise DatoInvalido(campo="servicio_id|zona", regla="exactamente_uno")
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            zona_id = None
            if zona is not None:
                # Se bloquea la zona: no se puede desactivar mientras se le publica una alerta.
                encontrada = await uow.zonas.obtener_por_codigo(zona)
                if encontrada is None or not encontrada.activa:
                    raise NoEncontrado(recurso="zona", id=zona.valor)
                zona_id = encontrada.id
            elif servicio_id is not None:
                servicio = await uow.servicios.obtener(servicio_id)
                if servicio is None or not servicio.activo:
                    raise NoEncontrado(recurso="servicio", id=str(servicio_id))
            alerta = AlertaOficial.publicar(
                nivel,
                mensaje,
                identidad.usuario_id,
                fecha_expiracion,
                ahora,
                servicio_id=servicio_id,
                zona_id=zona_id,
            )
            editable = await self._escritura.guardar_y_auditar(
                uow,
                alerta,
                zona.valor if zona else None,
                identidad,
                "ALERTA_PUBLICADA",
                ahora,
            )
            await uow.confirmar()
        return editable
