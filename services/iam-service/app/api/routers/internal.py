"""Rutas internas: sin `/api`, nunca expuestas por Traefik (Plan §4.1, C-15)."""

import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_obtener_contacto_usuario
from app.api.schemas.internal import ContactoUsuarioResponse
from app.application.use_cases.obtener_contacto_usuario import ObtenerContactoUsuario
from app.domain.exceptions import UsuarioNoEncontradoError
from app.infrastructure.observabilidad.metricas_contacto import CONSULTAS_CONTACTO

logger = logging.getLogger(__name__)

# Encabezados que agrega Traefik: si vienen, la petición no llegó desde dentro del clúster.
CABECERAS_PROXY = ("x-forwarded-for", "x-forwarded-host")

ResultadoContacto = Literal["ok", "no_encontrado", "rechazado_proxy"]


def _registrar(usuario_id: uuid.UUID | None, resultado: ResultadoContacto) -> None:
    # Sin fila en la bitácora (C-15): basta el log con el correlation_id del evento de catalog.
    # Nunca el correo.
    CONSULTAS_CONTACTO.labels(resultado=resultado).inc()
    logger.info(
        "Consulta de contacto",
        extra={"campos": {"usuario_id": usuario_id, "resultado": resultado}},
    )


def _usuario_id_de_la_ruta(request: Request) -> uuid.UUID | None:
    try:
        return uuid.UUID(request.path_params["usuario_id"])
    except (KeyError, ValueError):
        return None


async def rechazar_si_viene_por_proxy(request: Request) -> None:
    """Defensa adicional a la NetworkPolicy: lo que llega por Traefik recibe 404.

    Es una dependencia del router, de modo que corre antes de validar el UUID: por el proxy
    ni siquiera un UUID mal formado revela que la ruta existe.
    """
    if any(cabecera in request.headers for cabecera in CABECERAS_PROXY):
        _registrar(_usuario_id_de_la_ruta(request), "rechazado_proxy")
        raise UsuarioNoEncontradoError()


router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    include_in_schema=False,
    dependencies=[Depends(rechazar_si_viene_por_proxy)],
)


@router.get("/usuarios/{usuario_id}/contacto", response_model=ContactoUsuarioResponse)
async def contacto(
    usuario_id: uuid.UUID,
    obtener: Annotated[ObtenerContactoUsuario, Depends(get_obtener_contacto_usuario)],
) -> ContactoUsuarioResponse:
    try:
        usuario = await obtener.execute(usuario_id)
    except UsuarioNoEncontradoError:
        _registrar(usuario_id, "no_encontrado")
        raise
    _registrar(usuario_id, "ok")
    return ContactoUsuarioResponse(
        usuario_id=usuario_id,
        nombre=usuario.nombre_completo,
        email=usuario.email,
        idioma=usuario.idioma,
    )
