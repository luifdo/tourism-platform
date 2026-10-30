from uuid import UUID

from app.domain.entities.resena import Resena
from app.domain.errors import NoEncontrado
from app.domain.events.auditoria_registrada import AuditoriaRegistrada
from app.domain.ports.reloj import Reloj
from app.domain.ports.unidad_de_trabajo import FabricaUnidadDeTrabajo
from app.domain.value_objects.decision_moderacion import DecisionModeracion
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.resultado_auditoria import ResultadoAuditoria


class ModerarResena:
    """UC29: el Administrador publica u oculta una reseña y cierra sus reportes.

    En una sola transacción: el cambio de la reseña, los reportes resueltos, el evento que
    cambia el promedio (`resena.publicada` al sacarla de `OCULTA`, `resena.ocultada` al
    ocultarla) y la auditoría `MODERACION`, que se guarda siempre, también cuando la decisión
    no cambia nada (ocultar una ya oculta). Puede moderar cualquier reseña, esté o no en la
    cola: p. ej. una con datos personales que vio en la ficha.
    """

    def __init__(self, unidad_de_trabajo: FabricaUnidadDeTrabajo, reloj: Reloj) -> None:
        self._uow = unidad_de_trabajo
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        resena_id: UUID,
        version_esperada: int,
        decision: DecisionModeracion,
        motivo: str | None,
        ip_origen: str | None,
    ) -> Resena:
        identidad.exigir_rol(Rol.ADMIN)
        ahora = self._reloj.ahora()
        async with self._uow() as uow:
            resena = await uow.resenas.obtener(resena_id)
            if resena is None:
                raise NoEncontrado(resena=str(resena_id))
            anterior = resena.estado
            evento = resena.moderar(identidad.usuario_id, version_esperada, decision, motivo, ahora)
            resueltos = await uow.reportes.resolver_abiertos(resena.id, ahora)
            await uow.resenas.guardar(resena)
            if evento is not None:
                await uow.outbox.agregar(evento)
            await uow.outbox.agregar(
                AuditoriaRegistrada(
                    usuario_id=identidad.usuario_id,
                    accion="MODERACION",
                    resultado=ResultadoAuditoria.EXITO,
                    detalles={
                        "resena_id": str(resena.id),
                        "servicio_id": str(resena.servicio_id),
                        "decision": decision.value,
                        "motivo": (motivo or "").strip() or None,
                        "estado_anterior": anterior.value,
                        "estado_nuevo": resena.estado.value,
                        "reportes_resueltos": resueltos,
                    },
                    ip_origen=ip_origen,
                    ocurrido_en=ahora,
                )
            )
            await uow.confirmar()
        return resena
