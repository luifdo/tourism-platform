"""Helpers compartidos por los esquemas de respuesta."""

from typing import Any

from app.api.schemas.resena_publica_respuesta import ResenaPublicaRespuesta
from app.application.dto.pagina_resenas import PaginaResenas
from app.domain.value_objects.idioma import Idioma


def pagina_json(
    pagina: PaginaResenas, vista: type[ResenaPublicaRespuesta], idioma: Idioma
) -> dict[str, Any]:
    """`PaginaResenas`, `PaginaResenasPropias` o `PaginaResenasPrestador` según la vista."""
    return {
        "items": [vista.desde(r, idioma).a_json() for r in pagina.items],
        "pagina": pagina.pagina,
        "tamano": pagina.tamano,
        "total": pagina.total,
    }
