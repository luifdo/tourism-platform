"""Errores del dominio.

Cada error lleva un `codigo` estable igual al del contrato (`Error.error` en review.yaml) y
los datos necesarios para que el adaptador HTTP arme el mensaje en el idioma pedido; el
dominio no produce textos para el usuario.
"""

from typing import Any


class ErrorDominio(Exception):  # noqa: N818 (nombres en español: el sufijo va al inicio)
    codigo: str = "ERROR_DOMINIO"

    def __init__(self, **detalle: Any) -> None:
        self.detalle = detalle
        super().__init__(f"{self.codigo} {detalle}" if detalle else self.codigo)


class DatoInvalido(ErrorDominio):
    """Un dato no cumple una regla del dominio (HTTP 400)."""

    codigo = "VALIDACION"


class NoEncontrado(ErrorDominio):
    """No existe, está oculto o no pertenece al usuario (HTTP 404)."""

    codigo = "NO_ENCONTRADO"


class VersionDistinta(ErrorDominio):
    """El recurso cambió en el servidor desde que el usuario lo leyó (HTTP 409)."""

    codigo = "VERSION_DISTINTA"

    def __init__(self, version_actual: int) -> None:
        self.version_actual = version_actual
        super().__init__(version_actual=version_actual)


class RolNoPermitido(ErrorDominio):
    """El rol del usuario no puede ejecutar la operación (HTTP 403, se audita)."""

    codigo = "ROL_NO_PERMITIDO"
