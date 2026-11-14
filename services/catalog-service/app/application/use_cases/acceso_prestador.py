"""Reglas de acceso comunes a los casos de uso del prestador."""

from collections.abc import Callable

from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.errors import PerfilInactivo
from app.domain.ports.unidad_de_trabajo import UnidadDeTrabajo

FabricaUnidadDeTrabajo = Callable[[], UnidadDeTrabajo]


def exigir_perfil(perfil: PrestadorPerfil | None) -> PrestadorPerfil:
    """El rol `Prestador` llega en el JWT, pero el perfil existe solo cuando iam lo aprueba
    (`prestador.aprobado`). Mientras tanto se responde como perfil inactivo."""
    if perfil is None:
        raise PerfilInactivo(motivo="no_aprobado")
    return perfil
