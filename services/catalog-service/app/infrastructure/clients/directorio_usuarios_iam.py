"""Contacto de usuarios en iam (implementa DirectorioUsuarios).

`GET /internal/usuarios/{id}/contacto` (contracts/openapi/iam-interno.yaml): ruta interna,
sin gateway. 404 → el usuario no existe y no se envía el correo; un error o un tiempo de
espera agotado → DependenciaNoDisponible, y el consumidor reintenta.
"""

from uuid import UUID

import httpx

from app.application.dto.contacto_usuario import ContactoUsuario
from app.application.errores import DependenciaNoDisponible
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual


def _cabeceras_correlacion() -> dict[str, str]:
    """El log de iam se cruza con el evento que originó el correo (C-15 de iam)."""
    correlation_id = correlation_id_actual()
    return {"X-Correlation-ID": correlation_id} if correlation_id else {}


class DirectorioUsuariosIam:
    def __init__(self, cliente: httpx.AsyncClient) -> None:
        self._cliente = cliente

    async def contacto(self, usuario_id: UUID) -> ContactoUsuario | None:
        try:
            respuesta = await self._cliente.get(
                f"/internal/usuarios/{usuario_id}/contacto", headers=_cabeceras_correlacion()
            )
        except httpx.HTTPError as exc:
            raise DependenciaNoDisponible(servicio="iam") from exc
        if respuesta.status_code == 404:
            return None
        if respuesta.status_code != 200:
            raise DependenciaNoDisponible(servicio="iam", estado=respuesta.status_code)
        datos = respuesta.json()
        idioma = Idioma.EN if datos.get("idioma") == "en" else Idioma.ES
        return ContactoUsuario(
            usuario_id=UUID(datos["usuario_id"]),
            nombre=datos["nombre"],
            email=datos["email"],
            idioma=idioma,
        )
