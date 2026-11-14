import uuid
from typing import Any, Protocol

from app.domain.value_objects.enums import ResultadoAuditoria
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.domain.value_objects.filtro_bitacora import FiltroBitacora, PaginaBitacora


class AuditoriaRepository(Protocol):
    """Bitácora de auditoría de solo inserción (RNF-10)."""

    async def registrar(
        self,
        accion: str,
        resultado: ResultadoAuditoria,
        usuario_id: uuid.UUID | None,
        ip_origen: str | None,
        detalles: dict[str, Any],
    ) -> None: ...

    async def registrar_evento(self, evento: EventoAuditoria) -> bool:
        """Guarda un evento de otro servicio; False si su `event_id` ya estaba (C-04).

        Si `usuario_id` no existe en `usuario`, la fila queda con `usuario_id` nulo y el valor
        original en `detalles.usuario_id_no_registrado` (C-38).
        """
        ...

    async def listar(self, filtro: FiltroBitacora) -> PaginaBitacora:
        """UC33: filas que cumplen el filtro, por `fecha` descendente."""
        ...
