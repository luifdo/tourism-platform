from pydantic import ValidationError

from app.domain.errors import DatoInvalido


class EventoInvalido(Exception):  # noqa: N818 (nombres en español)
    """El mensaje no cumple el contrato (sobre, versión o payload): reintentarlo no lo arregla,
    va directo a la DLQ."""


# Errores que no se arreglan reintentando.
ERRORES_PERMANENTES = (EventoInvalido, ValidationError, DatoInvalido)
