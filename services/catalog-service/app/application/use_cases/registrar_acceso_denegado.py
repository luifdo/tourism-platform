from uuid import UUID

from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.catalogos import ResultadoAuditoria


class RegistrarAccesoDenegado:
    """ESC-04: todo acceso denegado por rol (`403 ROL_NO_PERMITIDO`) llega a la bitácora de iam.

    Se guarda como `auditoria.registrada` (acción `ACCESS_DENIED`) en el outbox, en su propia
    transacción: la operación denegada no escribió nada que confirmar.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self,
        usuario_id: UUID | None,
        rol: str | None,
        permitidos: list[str],
        metodo: str,
        ruta: str,
        ip_origen: str | None,
    ) -> None:
        evento = AuditoriaRegistrada(
            usuario_id=usuario_id,
            accion="ACCESS_DENIED",
            resultado=ResultadoAuditoria.DENEGADO,
            detalles={"rol": rol, "roles_permitidos": permitidos, "metodo": metodo, "ruta": ruta},
            ip_origen=ip_origen,
            ocurrido_en=self._reloj.ahora(),
        )
        async with self._uow() as uow:
            await uow.outbox.agregar(evento)
            await uow.confirmar()
