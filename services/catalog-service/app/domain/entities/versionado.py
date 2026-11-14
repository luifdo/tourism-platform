from dataclasses import dataclass

from app.domain.errors import VersionDistinta


@dataclass(kw_only=True)
class Versionado:
    """Concurrencia optimista (Plan §5.2): cada edición del usuario exige la versión que leyó.

    La versión es la que viaja en `ETag`/`If-Match` y en `servicio.publicado.version`.
    """

    version: int = 1

    def _verificar_version(self, esperada: int) -> None:
        if esperada != self.version:
            raise VersionDistinta(version_actual=self.version)

    def _avanzar_version(self) -> None:
        self.version += 1
