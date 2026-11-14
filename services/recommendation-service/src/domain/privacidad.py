"""Oculta datos personales que el turista escriba en el chat antes de guardarlos o enviarlos.

Ley 1581: al proveedor de IA no se le envía correo ni teléfono del turista. Solo se ocultan
patrones inequívocos (correos y celulares colombianos) para no dañar precios ni fechas.
"""

import re

OCULTO = "[dato personal oculto]"

_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celular colombiano: 3XX XXX XXXX, con o sin +57 y con espacios, puntos o guiones.
_CELULAR = re.compile(r"(?<!\d)(?:\+?57[\s.-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")


def ocultar_datos_personales(texto: str) -> str:
    return _CELULAR.sub(OCULTO, _CORREO.sub(OCULTO, texto))
