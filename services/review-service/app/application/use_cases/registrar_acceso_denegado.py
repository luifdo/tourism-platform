from typing import Any
from uuid import UUID

from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.domain.value_objects.resultado_auditoria import ResultadoAuditoria


class RegistrarAccesoDenegado:
    """ESC-04: los accesos denegados llegan a la bitácora de iam (acción `ACCESS_DENIED`).

    Se auditan `ROL_NO_PERMITIDO` (un rol que no puede usar la ruta) y `NO_ELEGIBLE` (un
    turista que intenta reseñar sin reserva finalizada). `motivo` es el código del error y
    `detalles` los datos de cada caso (roles permitidos, servicio).

    Se guarda en el outbox en su propia transacción: la operación denegada no escribió nada.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self,
        usuario_id: UUID | None,
        rol: str | None,
        motivo: str,
        detalles: dict[str, Any],
        metodo: str,
        ruta: str,
        ip_origen: str | None,
    ) -> None:
        evento = AuditoriaRegistrada(
            usuario_id=usuario_id,
            accion="ACCESS_DENIED",
            resultado=ResultadoAuditoria.DENEGADO,
            detalles={"motivo": motivo, "rol": rol, **detalles, "metodo": metodo, "ruta": ruta},
            ip_origen=ip_origen,
            ocurrido_en=self._reloj.ahora(),
        )
        async with self._uow() as uow:
            await uow.outbox.agregar(evento)
            await uow.confirmar()
