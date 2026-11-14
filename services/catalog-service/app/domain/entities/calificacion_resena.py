from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.errors import DatoInvalido


@dataclass(kw_only=True)
class CalificacionResena:
    """Puntuación de una reseña (proyección de `resena.publicada` y `resena.ocultada`).

    Una fila por reseña: si review-service la vuelve a publicar tras una moderación (UC29),
    se actualiza la misma fila y el promedio no cuenta doble. Una reseña que el Administrador
    oculta deja de contar en el promedio; si se vuelve a publicar, vuelve a contar.

    `ultimo_evento_en` es el `occurred_at` del último evento aplicado: un reintento puede
    traer una publicación vieja después de una ocultación nueva, y esa se ignora.
    """

    resena_id: UUID
    servicio_id: UUID
    puntuacion: int
    visible: bool = True
    ultimo_evento_en: datetime | None = None

    def __post_init__(self) -> None:
        _validar_puntuacion(self.puntuacion)

    @classmethod
    def desde_evento(
        cls,
        resena_id: UUID,
        servicio_id: UUID,
        puntuacion: int,
        visible: bool,
        ocurrido_en: datetime,
    ) -> "CalificacionResena":
        return cls(
            resena_id=resena_id,
            servicio_id=servicio_id,
            puntuacion=puntuacion,
            visible=visible,
            ultimo_evento_en=ocurrido_en,
        )

    def aplicar(self, puntuacion: int, visible: bool, ocurrido_en: datetime) -> bool:
        """Devuelve False si el evento es más viejo que el último aplicado (se ignora)."""
        if self.ultimo_evento_en is not None and ocurrido_en < self.ultimo_evento_en:
            return False
        _validar_puntuacion(puntuacion)
        self.puntuacion = puntuacion
        self.visible = visible
        self.ultimo_evento_en = ocurrido_en
        return True


def _validar_puntuacion(puntuacion: int) -> None:
    if not 1 <= puntuacion <= 5:
        raise DatoInvalido(campo="puntuacion", regla="rango", minimo=1, maximo=5)
