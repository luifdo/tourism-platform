"""Puerto de idempotencia de formularios (Plan §6.8): un reenvío de la PWA no se repite."""

from typing import Protocol

from app.application.dto.respuesta_guardada import RespuestaGuardada


class AlmacenIdempotencia(Protocol):
    async def reservar(self, clave: str) -> RespuestaGuardada | bool:
        """Marca la clave como en proceso.

        Devuelve True si se reservó (hay que ejecutar), la respuesta guardada si ya se ejecutó,
        o False si otro intento con la misma clave sigue en curso.
        """
        ...

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None: ...

    async def liberar(self, clave: str) -> None:
        """La operación falló: un reintento con la misma clave debe poder ejecutarse."""
        ...
