import uuid
from datetime import datetime
from typing import Protocol

from app.domain.entities.documento_verificacion import DocumentoVerificacion
from app.domain.value_objects.enums import EstadoDocumento, TipoDocumento
from app.domain.value_objects.filtro_prestadores import FiltroPrestadores, PaginaPrestadores


class DocumentoRepository(Protocol):
    async def agregar(self, documento: DocumentoVerificacion) -> DocumentoVerificacion:
        """Persiste el documento y lo devuelve con id y fecha_subida."""
        ...

    async def vigentes(self, usuario_id: uuid.UUID) -> list[DocumentoVerificacion]: ...

    async def historial(self, usuario_id: uuid.UUID) -> list[DocumentoVerificacion]:
        """Todos los documentos del usuario, incluidos los reemplazados, del más nuevo al
        más viejo."""
        ...

    async def find_by_id(self, documento_id: uuid.UUID) -> DocumentoVerificacion | None: ...

    async def retirar_vigente(self, usuario_id: uuid.UUID, tipo: TipoDocumento) -> None:
        """Marca `vigente = false` el documento vigente de ese tipo, si hay uno."""
        ...

    async def marcar_revisado(
        self,
        documento_id: uuid.UUID,
        estado: EstadoDocumento,
        revisado_por: uuid.UUID,
        revisado_en: datetime,
        motivo_rechazo: str | None,
    ) -> DocumentoVerificacion: ...

    async def listar_prestadores(self, filtro: FiltroPrestadores) -> PaginaPrestadores: ...
