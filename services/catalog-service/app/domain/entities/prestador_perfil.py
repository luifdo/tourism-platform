from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.versionado import Versionado
from app.domain.errors import PerfilInactivo
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(kw_only=True)
class PrestadorPerfil(Versionado):
    """Perfil comercial de un usuario aprobado como prestador (proyección de `prestador.aprobado`).

    `id` es el `prestador_id` que asigna iam-service al aprobarlo; `usuario_id` es el que llega
    en `X-Usuario-Id`.
    """

    id: UUID
    usuario_id: UUID
    razon_social: str | None
    telefono: str | None = None
    direccion: str | None = None
    politica_cancelacion: TextoTraducido | None = None
    activo: bool = True
    # `occurred_at` del último evento de iam aplicado (aprobado o suspendido). Un reintento
    # puede traer un evento viejo después de uno nuevo; ese se ignora.
    estado_iam_en: datetime | None = None

    @classmethod
    def aprobar(
        cls, prestador_id: UUID, usuario_id: UUID, razon_social: str | None
    ) -> "PrestadorPerfil":
        return cls(id=prestador_id, usuario_id=usuario_id, razon_social=razon_social)

    def reaprobar(self, razon_social: str | None) -> bool:
        """Aplica un `prestador.aprobado` repetido. Devuelve True si el perfil estaba suspendido."""
        if razon_social and razon_social != self.razon_social:
            self.razon_social = razon_social
            self._avanzar_version()
        if self.activo:
            return False
        self.activo = True
        self._avanzar_version()
        return True

    def suspender(self) -> bool:
        """Aplica `prestador.suspendido`. Devuelve True si el perfil estaba activo."""
        if not self.activo:
            return False
        self.activo = False
        self._avanzar_version()
        return True

    def es_evento_iam_viejo(self, ocurrido_en: datetime) -> bool:
        return self.estado_iam_en is not None and ocurrido_en < self.estado_iam_en

    def registrar_evento_iam(self, ocurrido_en: datetime) -> None:
        self.estado_iam_en = ocurrido_en

    def exigir_activo(self) -> None:
        if not self.activo:
            raise PerfilInactivo(prestador_id=str(self.id))

    def editar(
        self,
        version_esperada: int,
        telefono: str | None,
        direccion: str | None,
        politica_cancelacion: TextoTraducido | None,
    ) -> None:
        self.exigir_activo()
        self._verificar_version(version_esperada)
        self.telefono = telefono
        self.direccion = direccion
        self.politica_cancelacion = politica_cancelacion
        self._avanzar_version()
