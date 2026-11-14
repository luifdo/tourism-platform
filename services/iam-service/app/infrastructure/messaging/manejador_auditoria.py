"""Traduce los `auditoria.registrada` de la cola `iam.auditoria` a su caso de uso."""

from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.use_cases.registrar_evento_auditoria import RegistrarEventoAuditoria
from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.infrastructure.messaging.esquemas.auditoria_payload import AuditoriaPayload
from app.infrastructure.messaging.esquemas.sobre_evento import SobreEvento
from app.infrastructure.messaging.evento_invalido import EventoInvalido

COLA = "iam.auditoria"
CLAVES = ("auditoria.registrada",)
_MAX_SERVICIO_ORIGEN = 50  # longitud de bitacora_auditoria.servicio_origen


class ManejadorAuditoria:
    def __init__(self, registrar: RegistrarEventoAuditoria) -> None:
        self._registrar = registrar

    async def __call__(self, sobre: SobreEvento) -> ResultadoConsumo:
        if sobre.event_type != "auditoria.registrada":
            raise EventoInvalido(f"{COLA} no maneja {sobre.event_type}")
        if len(sobre.producer) > _MAX_SERVICIO_ORIGEN:
            raise EventoInvalido(f"producer de más de {_MAX_SERVICIO_ORIGEN} caracteres")
        payload = AuditoriaPayload.model_validate(sobre.payload)
        return await self._registrar.execute(
            EventoAuditoria(
                event_id=sobre.event_id,
                servicio_origen=sobre.producer,
                ocurrido_en=sobre.occurred_at,
                accion=payload.accion,
                # C-18: el contrato usa los nombres (EXITO); la base, los valores del SRS (Exito).
                resultado=ResultadoAuditoria[payload.resultado],
                usuario_id=payload.usuario_id,
                ip_origen=payload.ip_origen,
                detalles=payload.detalles,
                correlation_id=sobre.correlation_id,
            )
        )
