from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.entities.versionado import Versionado
from app.domain.errors import ZonaEnUso
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import PoligonoGeoJSON
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(kw_only=True)
class Zona(Versionado):
    """Zona turística con su polígono. Se carga una lista inicial y la Entidad la administra.

    No se borra: se desactiva, porque servicios, alertas y el histórico de demanda la usan.
    """

    id: UUID
    codigo: CodigoZona
    nombre: TextoTraducido
    poligono: PoligonoGeoJSON
    activa: bool = True

    @classmethod
    def crear(cls, codigo: CodigoZona, nombre: TextoTraducido, poligono: PoligonoGeoJSON) -> "Zona":
        return cls(id=uuid4(), codigo=codigo, nombre=nombre, poligono=poligono)

    def editar(
        self,
        version_esperada: int,
        codigo: CodigoZona,
        nombre: TextoTraducido,
        poligono: PoligonoGeoJSON,
    ) -> bool:
        """Devuelve True si cambió el polígono (hay que reasignar los servicios)."""
        self._verificar_version(version_esperada)
        cambio_poligono = poligono != self.poligono
        self.codigo = codigo
        self.nombre = nombre
        self.poligono = poligono
        self._avanzar_version()
        return cambio_poligono

    def desactivar(self, version_esperada: int, alertas_vigentes: int) -> bool:
        """Devuelve False si ya estaba inactiva (no hay nada que reasignar ni auditar)."""
        self._verificar_version(version_esperada)
        if not self.activa:
            return False
        if alertas_vigentes > 0:
            raise ZonaEnUso(zona=str(self.codigo), alertas_vigentes=alertas_vigentes)
        self.activa = False
        self._avanzar_version()
        return True
