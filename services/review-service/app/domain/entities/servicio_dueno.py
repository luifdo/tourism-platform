from dataclasses import dataclass
from uuid import UUID


@dataclass(kw_only=True)
class ServicioDueno:
    """Qué prestador es dueño de cada servicio, según `servicio.publicado` de catalog.

    Sirve para saber quién responde una reseña y si un reporte es del dueño. Review no llama
    a catalog: guarda esta proyección.
    """

    servicio_id: UUID
    prestador_usuario_id: UUID
    version: int

    def aplicar(self, version: int, prestador_usuario_id: UUID) -> bool:
        """Descarta lo que llegue con versión igual o menor; devuelve True si se aplicó."""
        if version <= self.version:
            return False
        self.version = version
        self.prestador_usuario_id = prestador_usuario_id
        return True

    def es_dueno(self, usuario_id: UUID) -> bool:
        return self.prestador_usuario_id == usuario_id
