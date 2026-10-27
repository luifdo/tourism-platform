from enum import StrEnum


class Idioma(StrEnum):
    ES = "es"
    EN = "en"

    @classmethod
    def desde_accept_language(cls, valor: str | None) -> "Idioma":
        """Toma el primer idioma de `Accept-Language`; todo lo que no sea inglés es español."""
        if not valor:
            return cls.ES
        primero = valor.split(",")[0].split(";")[0].strip().lower()
        return cls.EN if primero.split("-")[0] == "en" else cls.ES
