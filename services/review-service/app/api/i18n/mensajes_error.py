"""Mensajes de error del sistema en español e inglés.

El dominio solo entrega un código estable y datos (`ErrorDominio.detalle`); aquí se arma el
texto en el idioma de la petición. Un dato que falte en la plantilla se deja vacío, nunca
rompe la respuesta.
"""

from collections import defaultdict
from typing import Any

from app.domain.errors import ErrorDominio
from app.domain.value_objects.idioma import Idioma

_ES, _EN = Idioma.ES, Idioma.EN

MENSAJES: dict[str, dict[Idioma, str]] = {
    "NO_ENCONTRADO": {
        _ES: "El recurso solicitado no existe o no está disponible.",
        _EN: "The requested resource does not exist or is not available.",
    },
    "VERSION_DISTINTA": {
        _ES: "El registro cambió desde que lo abriste (versión actual: {version_actual}). "
        "Revisa los cambios antes de guardar.",
        _EN: "The record changed since you opened it (current version: {version_actual}). "
        "Review the changes before saving.",
    },
    "FALTA_IF_MATCH": {
        _ES: "Para editar hay que enviar la versión que se editó en la cabecera If-Match.",
        _EN: "Editing requires the edited version in the If-Match header.",
    },
    "ROL_NO_PERMITIDO": {
        _ES: "Tu rol no tiene permiso para esta operación.",
        _EN: "Your role is not allowed to perform this operation.",
    },
    "NO_ELEGIBLE": {
        _ES: "Solo puedes reseñar un servicio después de una reserva finalizada en él.",
        _EN: "You can only review a service after a completed booking with it.",
    },
    "NO_ES_DUENO": {
        _ES: "Esta reseña no es tuya o el servicio no es tuyo.",
        _EN: "This review or this service is not yours.",
    },
    "RESENA_PROPIA": {
        _ES: "No puedes reportar tu propia reseña; puedes editarla.",
        _EN: "You cannot report your own review; you can edit it.",
    },
    "YA_RESENADO": {
        _ES: "Ya reseñaste este servicio. Puedes editar tu reseña.",
        _EN: "You already reviewed this service. You can edit your review.",
    },
    "RESENA_EN_MODERACION": {
        _ES: "La reseña está en revisión u oculta por moderación y no admite este cambio.",
        _EN: "The review is under moderation or hidden and cannot be changed this way.",
    },
    "YA_REPORTADA": {
        _ES: "Ya reportaste esta reseña; el equipo de moderación la revisará.",
        _EN: "You already reported this review; the moderation team will check it.",
    },
    "DEMASIADOS_REPORTES": {
        _ES: "Llegaste al límite de {limite} reportes por hora. Intenta de nuevo en "
        "{retry_after} segundos.",
        _EN: "You reached the limit of {limite} reports per hour. Try again in "
        "{retry_after} seconds.",
    },
    "NO_AUTENTICADO": {
        _ES: "Debes iniciar sesión para esta operación.",
        _EN: "You must sign in to perform this operation.",
    },
    "DEPENDENCIA_NO_DISPONIBLE": {
        _ES: "Un servicio interno no respondió a tiempo. Intenta de nuevo en un momento.",
        _EN: "An internal service did not respond in time. Try again shortly.",
    },
    "METODO_NO_PERMITIDO": {
        _ES: "Esta ruta no admite el método {metodo}.",
        _EN: "This route does not accept the {metodo} method.",
    },
    "ERROR_INTERNO": {
        _ES: "Ocurrió un error inesperado. Intenta de nuevo; si persiste, informa el código "
        "de correlación.",
        _EN: "An unexpected error occurred. Try again; if it persists, report the correlation ID.",
    },
}

# Errores de validación: el texto depende de la regla que se incumplió.
VALIDACION: dict[str, dict[Idioma, str]] = {
    "obligatorio": {
        _ES: "El campo «{campo}» es obligatorio.",
        _EN: "The field '{campo}' is required.",
    },
    "rango": {
        _ES: "El campo «{campo}» debe estar entre {minimo} y {maximo}.",
        _EN: "The field '{campo}' must be between {minimo} and {maximo}.",
    },
    "maximo": {
        _ES: "El campo «{campo}» admite como máximo {maximo}.",
        _EN: "The field '{campo}' allows at most {maximo}.",
    },
    "requiere": {
        _ES: "El campo «{campo}» requiere también: {requiere}.",
        _EN: "The field '{campo}' also requires: {requiere}.",
    },
    "repetido": {
        _ES: "El campo «{campo}» tiene valores repetidos.",
        _EN: "The field '{campo}' has repeated values.",
    },
    "formato": {
        _ES: "El campo «{campo}» no tiene un formato válido.",
        _EN: "The field '{campo}' has an invalid format.",
    },
}

_GENERICO_VALIDACION = {
    _ES: "El campo «{campo}» no es válido.",
    _EN: "The field '{campo}' is not valid.",
}


def _formatear(plantilla: str, datos: dict[str, Any]) -> str:
    return plantilla.format_map(defaultdict(str, datos))


# Los datos van como diccionario (no **kwargs): el detalle de un error puede traer claves
# como `regla` o `idioma` que chocarían con los parámetros.
def mensaje_validacion(regla: str, idioma: Idioma, datos: dict[str, Any]) -> str:
    return _formatear(VALIDACION.get(regla, _GENERICO_VALIDACION)[idioma], datos)


def mensaje_error(error: ErrorDominio, idioma: Idioma) -> str:
    if error.codigo == "VALIDACION":
        return mensaje_validacion(str(error.detalle.get("regla", "")), idioma, error.detalle)
    return mensaje_codigo(error.codigo, idioma, error.detalle)


def mensaje_codigo(codigo: str, idioma: Idioma, datos: dict[str, Any] | None = None) -> str:
    plantilla = MENSAJES.get(codigo, MENSAJES["ERROR_INTERNO"])[idioma]
    return _formatear(plantilla, datos or {})
