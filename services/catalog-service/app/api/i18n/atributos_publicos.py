"""Atributos para la ficha pública: mismos bloques que edita el prestador, en el idioma pedido.

* Los textos `{"es", "en"}` pasan a una sola cadena (español si falta la traducción).
* Los códigos fijos (`DE_MAR`, `SIN_SENAL`...) se mantienen y sus etiquetas van aparte, en
  `etiquetas`, para que la PWA y el chatbot muestren el mismo texto.
"""

from typing import Any

from app.api.i18n.etiquetas import ETIQUETAS
from app.api.schemas.atributos.atributos_servicio_datos import AtributosServicioDatos
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.texto_traducido import TextoTraducido

_IDIOMAS = {"es", "en"}


def atributos_publicos(
    atributos: AtributosServicio, idioma: Idioma
) -> tuple[dict[str, Any], dict[str, str]]:
    """Devuelve los atributos localizados y las etiquetas de los códigos que aparecen."""
    crudo = AtributosServicioDatos.desde(atributos).model_dump(mode="json", exclude_none=True)
    etiquetas: dict[str, str] = {}
    return _localizar(crudo, idioma, etiquetas), dict(sorted(etiquetas.items()))


def _localizar(valor: Any, idioma: Idioma, etiquetas: dict[str, str]) -> Any:
    if isinstance(valor, dict):
        if "es" in valor and set(valor) <= _IDIOMAS:
            return TextoTraducido(**valor).en_idioma(idioma)[0]
        return {k: _localizar(v, idioma, etiquetas) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_localizar(v, idioma, etiquetas) for v in valor]
    if isinstance(valor, str) and valor in ETIQUETAS:
        etiquetas[valor] = ETIQUETAS[valor][idioma]  # type: ignore[index]
    return valor
