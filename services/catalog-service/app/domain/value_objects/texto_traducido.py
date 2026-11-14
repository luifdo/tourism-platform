from dataclasses import dataclass

from app.domain.errors import DatoInvalido
from app.domain.value_objects.idioma import Idioma


@dataclass(frozen=True, slots=True)
class TextoTraducido:
    """Texto escrito por un usuario en español (obligatorio) y, opcionalmente, en inglés."""

    es: str
    en: str | None = None

    def __post_init__(self) -> None:
        es = self.es.strip() if self.es else ""
        en = self.en.strip() if self.en else None
        if not es:
            raise DatoInvalido(campo="es", regla="obligatorio")
        object.__setattr__(self, "es", es)
        object.__setattr__(self, "en", en or None)

    def en_idioma(self, idioma: Idioma) -> tuple[str, Idioma]:
        """Devuelve el texto y el idioma realmente usado (español si falta la traducción)."""
        if idioma is Idioma.EN and self.en:
            return self.en, Idioma.EN
        return self.es, Idioma.ES

    def a_dict(self) -> dict[str, str]:
        return {"es": self.es} | ({"en": self.en} if self.en else {})
