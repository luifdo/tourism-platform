from uuid import UUID

from app.api.schemas.resena_guardar import ResenaGuardar


class ResenaCrear(ResenaGuardar):
    """Cuerpo de `POST /resenas` (contrato `ResenaCrear`): lo mismo que editar y el servicio."""

    servicio_id: UUID
