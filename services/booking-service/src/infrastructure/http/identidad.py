"""Identidad que reenvía Traefik tras ForwardAuth (`X-Usuario-Id`, `X-Usuario-Rol`).

Los encabezados se muestran en Swagger para poder probar sin el gateway; en el clúster
solo los pone Traefik, porque la política de red no deja llegar tráfico de otro lado (Plan §7.4).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from application.auditoria import RegistrarAccesoDenegado
from application.errores import RolNoPermitido
from infrastructure.http.errores import NoAutenticado, correlation_id


class Rol(StrEnum):
    TURISTA = "Turista"
    PRESTADOR = "Prestador"
    ENTIDAD = "Entidad"
    ADMIN = "Admin"


@dataclass(frozen=True)
class Identidad:
    usuario_id: UUID
    rol: Rol


async def identidad(
    request: Request,
    x_usuario_id: Annotated[
        str | None, Header(description="Lo agrega Traefik. En Swagger, escriba el id del usuario.")
    ] = None,
    x_usuario_rol: Annotated[
        str | None, Header(description="Lo agrega Traefik: `Turista`, `Prestador`, `Entidad` o `Admin`.")
    ] = None,
) -> Identidad:
    if not x_usuario_id or not x_usuario_rol:
        raise NoAutenticado("Falta la identidad del usuario (X-Usuario-Id y X-Usuario-Rol).")
    try:
        usuario_id = UUID(x_usuario_id)
    except ValueError as exc:
        raise NoAutenticado("X-Usuario-Id no es un UUID válido.") from exc
    try:
        rol = Rol(x_usuario_rol)
    except ValueError as exc:
        await _denegar(request, usuario_id, x_usuario_rol)
        raise RolNoPermitido(f"Rol desconocido: {x_usuario_rol}.") from exc
    return Identidad(usuario_id, rol)


async def _denegar(request: Request, usuario_id: UUID, rol: str) -> None:
    """Todo acceso denegado por rol queda en la bitácora del Módulo 1 (ESC-04)."""
    await RegistrarAccesoDenegado(request.app.state.contenedor.ctx)(
        usuario_id, f"{request.method} {request.url.path}", rol, correlation_id(request)
    )


def requiere(*roles: Rol):
    async def _dependencia(request: Request, quien: Annotated[Identidad, Depends(identidad)]) -> Identidad:
        if quien.rol not in roles:
            await _denegar(request, quien.usuario_id, quien.rol.value)
            permitidos = " o ".join(r.value for r in roles)
            raise RolNoPermitido(f"Esta operación es solo para el rol {permitidos}.")
        return quien

    return _dependencia


Turista = Annotated[Identidad, Depends(requiere(Rol.TURISTA))]
Prestador = Annotated[Identidad, Depends(requiere(Rol.PRESTADOR))]
TuristaOPrestador = Annotated[Identidad, Depends(requiere(Rol.TURISTA, Rol.PRESTADOR))]
