import uuid
from typing import Any

from sqlalchemy import DateTime, String, case, cast, exists, func, literal, null, select
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.domain.value_objects.filtro_bitacora import EntradaBitacora, FiltroBitacora, PaginaBitacora
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

    async def listar(self, filtro: FiltroBitacora) -> PaginaBitacora:
        b = BitacoraAuditoria
        condiciones = []
        if filtro.usuario_id is not None:
            condiciones.append(b.usuario_id == filtro.usuario_id)
        if filtro.accion is not None:
            condiciones.append(b.accion == filtro.accion)
        if filtro.resultado is not None:
            condiciones.append(b.resultado == filtro.resultado)
        if filtro.servicio_origen is not None:
            condiciones.append(b.servicio_origen == filtro.servicio_origen)
        if filtro.desde is not None:
            condiciones.append(b.fecha >= filtro.desde)
        if filtro.hasta is not None:
            condiciones.append(b.fecha < filtro.hasta)
        total = await self._session.scalar(select(func.count()).select_from(b).where(*condiciones))
        filas = await self._session.scalars(
            select(b)
            .where(*condiciones)
            .order_by(b.fecha.desc(), b.id.desc())
            .limit(filtro.tamano)
            .offset((filtro.pagina - 1) * filtro.tamano)
        )
        return PaginaBitacora(
            items=[_a_entrada(f) for f in filas],
            total=total or 0,
            pagina=filtro.pagina,
            tamano=filtro.tamano,
        )


def _a_entrada(fila: BitacoraAuditoria) -> EntradaBitacora:
    return EntradaBitacora(
        id=fila.id,
        fecha=fila.fecha,
        usuario_id=fila.usuario_id,
        accion=fila.accion,
        resultado=fila.resultado,
        servicio_origen=fila.servicio_origen,
        # INET llega como objeto de ipaddress.
        ip_origen=str(fila.ip_origen) if fila.ip_origen is not None else None,
        detalles=fila.detalles,
        correlation_id=fila.correlation_id,
        event_id=fila.event_id,
    )
