from typing import Annotated

from fastapi import Header, Response

from app.domain.value_objects.idioma import Idioma


def idioma_peticion(
    response: Response,
    accept_language: Annotated[str | None, Header()] = None,
) -> Idioma:
    """Idioma de la petición (`Accept-Language`, español por defecto).

    Lo declara en `Content-Language`: los textos del sistema y las etiquetas salen en ese
    idioma; un texto escrito por un usuario sin traducción sale en español.
    """
    idioma = Idioma.desde_accept_language(accept_language)
    response.headers["Content-Language"] = idioma.value
    return idioma
