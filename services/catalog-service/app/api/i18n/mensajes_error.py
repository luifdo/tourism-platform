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
    "PERFIL_INACTIVO": {
        _ES: "Tu perfil de prestador no está aprobado o fue suspendido.",
        _EN: "Your provider profile is not approved or has been suspended.",
    },
    "ROL_NO_PERMITIDO": {
        _ES: "Tu rol no tiene permiso para esta operación.",
        _EN: "Your role is not allowed to perform this operation.",
    },
    "ZONA_EN_USO": {
        _ES: "La zona tiene {alertas_vigentes} alerta(s) vigente(s); retíralas antes de "
        "desactivarla.",
        _EN: "The zone has {alertas_vigentes} active alert(s); withdraw them before "
        "deactivating it.",
    },
    "CODIGO_EXISTENTE": {
        _ES: "Ya existe una zona con ese código.",
        _EN: "A zone with that code already exists.",
    },
    "ALERTA_RETIRADA": {
        _ES: "La alerta ya fue retirada y no se puede editar; publica una nueva.",
        _EN: "The alert has been withdrawn and cannot be edited; publish a new one.",
    },
    "NO_AUTENTICADO": {
        _ES: "Debes iniciar sesión para esta operación.",
        _EN: "You must sign in to perform this operation.",
    },
    "DEPENDENCIA_NO_DISPONIBLE": {
        _ES: "Un servicio externo no respondió a tiempo. Intenta de nuevo en un momento; "
        "si buscabas una dirección, puedes marcar el punto en el mapa.",
        _EN: "An external service did not respond in time. Try again shortly; if you were "
        "looking up an address, you can mark the point on the map.",
    },
    "SOLICITUD_EN_PROCESO": {
        _ES: "Este envío ya se está procesando. Espera unos segundos y vuelve a intentarlo.",
        _EN: "This submission is already being processed. Wait a few seconds and try again.",
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
    "minimo": {
        _ES: "El campo «{campo}» debe ser como mínimo {minimo}.",
        _EN: "The field '{campo}' must be at least {minimo}.",
    },
    "maximo": {
        _ES: "El campo «{campo}» admite como máximo {maximo}.",
        _EN: "The field '{campo}' allows at most {maximo}.",
    },
    "mayor_que": {
        _ES: "El campo «{campo}» no puede ser mayor que «{otro}».",
        _EN: "The field '{campo}' cannot be greater than '{otro}'.",
    },
    "requiere": {
        _ES: "El campo «{campo}» requiere también: {requiere}.",
        _EN: "The field '{campo}' also requires: {requiere}.",
    },
    "numero": {
        _ES: "El campo «{campo}» debe ser un número.",
        _EN: "The field '{campo}' must be a number.",
    },
    "patron": {
        _ES: "El campo «{campo}» solo admite minúsculas, números y guiones (2 a 40).",
        _EN: "The field '{campo}' only allows lowercase letters, digits and hyphens (2 to 40).",
    },
    "formato": {
        _ES: "El campo «{campo}» no tiene un formato válido.",
        _EN: "The field '{campo}' has an invalid format.",
    },
    "cuatro_valores": {
        _ES: "«bbox» debe tener cuatro valores: minLon,minLat,maxLon,maxLat.",
        _EN: "'bbox' must have four values: minLon,minLat,maxLon,maxLat.",
    },
    "minimo_menor_que_maximo": {
        _ES: "En «bbox» los mínimos deben ser menores que los máximos.",
        _EN: "In 'bbox' the minimums must be lower than the maximums.",
    },
    "tipo": {
        _ES: "La geometría debe ser Polygon o MultiPolygon.",
        _EN: "The geometry must be a Polygon or MultiPolygon.",
    },
    "geojson": {
        _ES: "La geometría no es un GeoJSON válido.",
        _EN: "The geometry is not valid GeoJSON.",
    },
    "sin_poligonos": {
        _ES: "La geometría no contiene polígonos.",
        _EN: "The geometry contains no polygons.",
    },
    "sin_anillos": {
        _ES: "Cada polígono necesita al menos un anillo.",
        _EN: "Each polygon needs at least one ring.",
    },
    "anillo_minimo_4_puntos": {
        _ES: "Cada anillo del polígono necesita al menos 4 puntos.",
        _EN: "Each polygon ring needs at least 4 points.",
    },
    "anillo_cerrado": {
        _ES: "Cada anillo debe terminar en el mismo punto en que empieza.",
        _EN: "Each ring must end at the same point where it starts.",
    },
    "poligono_invalido": {
        _ES: "El polígono no es válido: sus bordes se cruzan o se tocan a sí mismos.",
        _EN: "The polygon is not valid: its edges cross or touch themselves.",
    },
    "repetido": {
        _ES: "El campo «{campo}» tiene valores repetidos.",
        _EN: "The field '{campo}' has repeated values.",
    },
    "bloque_obligatorio": {
        _ES: "Para el tipo {tipo} hay que llenar «{campo}».",
        _EN: "Type {tipo} requires '{campo}'.",
    },
    "bloque_no_permitido": {
        _ES: "«{campo}» no corresponde al tipo {tipo}.",
        _EN: "'{campo}' does not apply to type {tipo}.",
    },
    "recomendacion_sin_medio": {
        _ES: "La recomendación de dinero no coincide con los medios de pago aceptados.",
        _EN: "The money recommendation does not match the accepted payment methods.",
    },
    "punto_lon_lat": {
        _ES: "Cada punto debe ser [longitud, latitud].",
        _EN: "Each point must be [longitude, latitude].",
    },
    "bucket_no_permitido": {
        _ES: "Las imágenes deben subirse con la URL que entrega la plataforma.",
        _EN: "Images must be uploaded with the URL provided by the platform.",
    },
    "exactamente_uno": {
        _ES: "Indica un servicio o una zona, pero no ambos.",
        _EN: "Specify either a service or a zone, but not both.",
    },
    "plazo_maximo": {
        _ES: "La fecha de «{campo}» no puede estar a más de {dias} días.",
        _EN: "The '{campo}' date cannot be more than {dias} days away.",
    },
    "futura": {
        _ES: "La fecha de «{campo}» debe ser futura.",
        _EN: "The '{campo}' date must be in the future.",
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
