from enum import StrEnum


class EstadoResena(StrEnum):
    """`PUBLICADA` es visible; `EN_REVISION` está oculta esperando al Administrador pero su
    puntuación sigue contando; `OCULTA` es decisión del Administrador y no cuenta."""

    PUBLICADA = "PUBLICADA"
    EN_REVISION = "EN_REVISION"
    OCULTA = "OCULTA"
