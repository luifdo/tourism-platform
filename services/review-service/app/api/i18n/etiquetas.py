"""Etiquetas en español e inglés de los valores fijos de review.

La API devuelve el código estable (`LIMPIEZA`) y su etiqueta en el idioma pedido, para que
la PWA, el chatbot y cualquier otro cliente muestren el mismo texto. El texto que escribe el
usuario (comentario, respuesta) no se traduce.
"""

from enum import StrEnum

from app.domain.value_objects.aspecto import Aspecto
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.idioma import Idioma

_ES, _EN = Idioma.ES, Idioma.EN

# Autor anónimo de toda reseña: nunca el nombre ni el id del turista.
AUTOR = {_ES: "Turista verificado", _EN: "Verified tourist"}

ETIQUETAS: dict[StrEnum, dict[Idioma, str]] = {
    Aspecto.LIMPIEZA: {_ES: "Limpieza", _EN: "Cleanliness"},
    Aspecto.ATENCION: {_ES: "Atención", _EN: "Service"},
    Aspecto.CALIDAD_PRECIO: {_ES: "Calidad-precio", _EN: "Value for money"},
    Aspecto.SEGURIDAD: {_ES: "Seguridad", _EN: "Safety"},
    Aspecto.GUIANZA: {_ES: "Guianza", _EN: "Guiding"},
    EstadoResena.PUBLICADA: {_ES: "Publicada", _EN: "Published"},
    EstadoResena.EN_REVISION: {_ES: "En revisión", _EN: "Under review"},
    EstadoResena.OCULTA: {_ES: "Oculta", _EN: "Hidden"},
}


def etiqueta(valor: StrEnum, idioma: Idioma) -> str:
    return ETIQUETAS[valor][idioma]
