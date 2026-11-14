from app.domain.errors import DatoInvalido

PUNTUACION_MINIMA = 1
PUNTUACION_MAXIMA = 5


def validar_puntuacion(valor: int, campo: str) -> None:
    # bool es subclase de int: True no es una puntuación.
    if isinstance(valor, bool) or not PUNTUACION_MINIMA <= valor <= PUNTUACION_MAXIMA:
        raise DatoInvalido(
            campo=campo, regla="rango", minimo=PUNTUACION_MINIMA, maximo=PUNTUACION_MAXIMA
        )


def texto_limpio(valor: str | None, campo: str, maximo: int) -> str | None:
    """Quita los espacios de los extremos; vacío equivale a no escribir nada."""
    limpio = (valor or "").strip()
    if len(limpio) > maximo:
        raise DatoInvalido(campo=campo, regla="maximo", maximo=maximo)
    return limpio or None
