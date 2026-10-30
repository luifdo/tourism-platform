import uuid
from typing import Any

from sqlalchemy import DateTime, String, case, cast, exists, literal, null, select
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual
from app.infrastructure.persistence.models import BitacoraAuditoria, Usuario


class SqlAlchemyAuditoriaRepository:
    """Implementa AuditoriaRepository sobre bitacora_auditoria (solo INSERT)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar(
        self,
        accion: str,
        resultado: ResultadoAuditoria,
        usuario_id: uuid.UUID | None,
        ip_origen: str | None,
        detalles: dict[str, Any],
    ) -> None:
        self._session.add(
            BitacoraAuditoria(
                accion=accion,
                resultado=resultado,
                usuario_id=usuario_id,
                ip_origen=ip_origen,
                detalles=detalles,
                correlation_id=correlation_id_actual(),
            )
        )
        await self._session.flush()

    async def registrar_evento(self, evento: EventoAuditoria) -> bool:
        """Un solo INSERT ... SELECT ... ON CONFLICT (event_id) DO NOTHING (C-04).

        El usuario se resuelve en la misma sentencia (C-38): si no existe en `usuario`, la fila
        queda con `usuario_id` nulo y el id recibido en `detalles.usuario_id_no_registrado`,
        en lugar de chocar con la llave foránea.
        """
        tabla = BitacoraAuditoria.__table__
        detalles = cast(literal(evento.detalles, JSONB), JSONB)
        if evento.usuario_id is None:
            usuario_id, detalles_finales = null(), detalles
        else:
            id_recibido = cast(literal(evento.usuario_id, UUID(as_uuid=True)), UUID(as_uuid=True))
            existe = exists().where(Usuario.id == id_recibido)
            usuario_id = case((existe, id_recibido), else_=null())
            no_registrado = {
                **evento.detalles,
                "usuario_id_no_registrado": str(evento.usuario_id),
            }
            detalles_finales = case(
                (existe, detalles), else_=cast(literal(no_registrado, JSONB), JSONB)
            )

        valores = {
            "event_id": cast(literal(evento.event_id, UUID(as_uuid=True)), UUID(as_uuid=True)),
            "usuario_id": usuario_id,
            "accion": cast(literal(evento.accion), String),
            "resultado": cast(literal(evento.resultado.value), tabla.c.resultado.type),
            "servicio_origen": cast(literal(evento.servicio_origen), String),
            "ip_origen": cast(literal(evento.ip_origen), INET),
            "detalles": detalles_finales,
            "fecha": cast(literal(evento.ocurrido_en, DateTime(timezone=True)), DateTime(True)),
            "correlation_id": cast(literal(evento.correlation_id), String),
        }
        sentencia = (
            insert(tabla)
            .from_select(list(valores), select(*valores.values()))
            .on_conflict_do_nothing(index_elements=["event_id"])
            .returning(tabla.c.id)
        )
        resultado = await self._session.execute(sentencia)
        return resultado.scalar_one_or_none() is not None
