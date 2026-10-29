from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.domain.entities.versionado import Versionado
from app.domain.errors import AlertaRetirada, DatoInvalido
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.texto_traducido import TextoTraducido

# Una alerta olvidada no queda vigente para siempre.
VIGENCIA_MAXIMA = timedelta(days=365)


@dataclass(kw_only=True)
class AlertaOficial(Versionado):
    """Aviso oficial de la Entidad sobre un servicio o sobre una zona completa (UC26).

    No se borra: se retira. El destino (servicio o zona) no cambia; para avisar en otro
    lugar se publica otra alerta. Editar exige la versión que se leyó (`If-Match`): varias
    personas de la Entidad pueden administrar las mismas alertas.
    """

    id: UUID
    nivel: NivelAlerta
    mensaje: TextoTraducido
    entidad_usuario_id: UUID
    fecha_expiracion: datetime
    creada_en: datetime
    servicio_id: UUID | None = None
    zona_id: UUID | None = None
    activa: bool = True

    @classmethod
    def publicar(
        cls,
        nivel: NivelAlerta,
        mensaje: TextoTraducido,
        entidad_usuario_id: UUID,
        fecha_expiracion: datetime,
        ahora: datetime,
        servicio_id: UUID | None = None,
        zona_id: UUID | None = None,
    ) -> "AlertaOficial":
        if (servicio_id is None) == (zona_id is None):
            raise DatoInvalido(campo="servicio_id|zona", regla="exactamente_uno")
        _validar_expiracion(fecha_expiracion, ahora)
        return cls(
            id=uuid4(),
            nivel=nivel,
            mensaje=mensaje,
            entidad_usuario_id=entidad_usuario_id,
            fecha_expiracion=fecha_expiracion,
            creada_en=ahora,
            servicio_id=servicio_id,
            zona_id=zona_id,
        )

    def editar(
        self,
        version_esperada: int,
        nivel: NivelAlerta,
        mensaje: TextoTraducido,
        fecha_expiracion: datetime,
        ahora: datetime,
    ) -> None:
        """Corregir el mensaje o el nivel, o extender (o acortar) la vigencia."""
        self._verificar_version(version_esperada)
        if not self.activa:
            raise AlertaRetirada(alerta=str(self.id))
        _validar_expiracion(fecha_expiracion, ahora)
        self.nivel = nivel
        self.mensaje = mensaje
        self.fecha_expiracion = fecha_expiracion
        self._avanzar_version()

    def vigente(self, ahora: datetime) -> bool:
        return self.activa and self.fecha_expiracion > ahora

    def desactivar(self) -> bool:
        """Retira la alerta. Devuelve False si ya estaba retirada (nada que auditar)."""
        if not self.activa:
            return False
        self.activa = False
        self._avanzar_version()
        return True


def _validar_expiracion(fecha_expiracion: datetime, ahora: datetime) -> None:
    if fecha_expiracion <= ahora:
        raise DatoInvalido(campo="fecha_expiracion", regla="futura")
    if fecha_expiracion > ahora + VIGENCIA_MAXIMA:
        raise DatoInvalido(
            campo="fecha_expiracion", regla="plazo_maximo", dias=VIGENCIA_MAXIMA.days
        )
