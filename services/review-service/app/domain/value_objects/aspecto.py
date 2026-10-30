from enum import StrEnum


class Aspecto(StrEnum):
    """Aspecto que el turista puede calificar aparte de la puntuación general."""

    LIMPIEZA = "LIMPIEZA"
    ATENCION = "ATENCION"
    CALIDAD_PRECIO = "CALIDAD_PRECIO"
    SEGURIDAD = "SEGURIDAD"
    GUIANZA = "GUIANZA"
