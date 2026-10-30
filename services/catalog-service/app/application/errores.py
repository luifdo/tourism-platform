"""Errores de la capa de aplicación: no son reglas del negocio sino de la operación.

Heredan de ErrorDominio para que el adaptador HTTP los traduzca igual (código y mensaje en el
idioma pedido).
"""

from app.domain.errors import ErrorDominio


class NoAutenticado(ErrorDominio):
    """Faltan o son inválidas las cabeceras de identidad que agrega Traefik (HTTP 401)."""

    codigo = "NO_AUTENTICADO"


class DependenciaNoDisponible(ErrorDominio):
    """Un servicio externo (Nominatim, SeaweedFS) no respondió a tiempo (HTTP 503)."""

    codigo = "DEPENDENCIA_NO_DISPONIBLE"


class SolicitudEnProceso(ErrorDominio):
    """Llegó un reintento con la misma Idempotency-Key mientras el primero sigue (HTTP 409)."""

    codigo = "SOLICITUD_EN_PROCESO"


class FaltaIfMatch(ErrorDominio):
    """Una edición llegó sin la versión que se editó en `If-Match` (HTTP 428)."""

    codigo = "FALTA_IF_MATCH"
