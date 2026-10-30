"""Identidad del usuario a partir de las cabeceras que agrega Traefik tras validar el JWT.

Traefik (ForwardAuth contra iam) borra las cabeceras `X-Usuario-*` que mande el cliente y
pone las suyas; el servicio solo es accesible a través del gateway (NetworkPolicy en k8s).
"""

from typing import Annotated
from uuid import UUID

from fastapi import Header

from app.application.errores import NoAutenticado
from app.domain.errors import RolNoPermitido
from app.domain.value_objects.identidad import Identidad, Rol


def identidad_peticion(
    x_usuario_id: Annotated[str | None, Header(include_in_schema=False)] = None,
    x_usuario_rol: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> Identidad:
    if not x_usuario_id or not x_usuario_rol:
        raise NoAutenticado()
    try:
        usuario_id = UUID(x_usuario_id)
    except ValueError as exc:
        raise NoAutenticado() from exc
    try:
        rol = Rol(x_usuario_rol)
    except ValueError as exc:
        # Un rol que este servicio no conoce está autenticado pero no tiene permisos aquí.
        raise RolNoPermitido(rol=x_usuario_rol, permitidos=[r.value for r in Rol]) from exc
    return Identidad(usuario_id=usuario_id, rol=rol)
