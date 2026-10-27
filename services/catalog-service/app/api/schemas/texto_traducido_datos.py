from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.texto_traducido import TextoTraducido


class TextoTraducidoDatos(BaseModel):
    """Texto en ambos idiomas, como lo escribe y lo edita su autor (`{"es", "en"}`)."""

    model_config = ConfigDict(extra="forbid")

    es: str = Field(min_length=1)
    en: str | None = Field(default=None, min_length=1)

    def a_dominio(self) -> TextoTraducido:
        return TextoTraducido(es=self.es, en=self.en)

    @classmethod
    def desde(cls, texto: TextoTraducido) -> "TextoTraducidoDatos":
        return cls(es=texto.es, en=texto.en)
