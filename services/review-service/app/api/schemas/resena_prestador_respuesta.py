from app.api.schemas.resena_propia_respuesta import ResenaPropiaRespuesta


class ResenaPrestadorRespuesta(ResenaPropiaRespuesta):
    """La reseña vista por el prestador dueño (contrato `ResenaPrestador`): sigue anónima,
    con su estado (publicada o en revisión) y la versión para responder con `If-Match`."""
