from dataclasses import dataclass, field

from app.domain.value_objects.aspecto import Aspecto
from app.domain.value_objects.comun import texto_limpio, validar_puntuacion

COMENTARIO_MAXIMO = 2000


@dataclass(frozen=True)
class ContenidoResena:
    """Lo que escribe el turista: puntuación general, aspectos opcionales y comentario.

    Solo se guardan los aspectos que calificó. El comentario se muestra tal cual, sin
    traducir.
    """

    puntuacion: int
    aspectos: dict[Aspecto, int] = field(default_factory=dict)
    comentario: str | None = None

    def __post_init__(self) -> None:
        validar_puntuacion(self.puntuacion, "puntuacion")
        for aspecto, valor in self.aspectos.items():
            validar_puntuacion(valor, f"aspectos.{aspecto.value}")
        comentario = texto_limpio(self.comentario, "comentario", COMENTARIO_MAXIMO)
        object.__setattr__(self, "comentario", comentario)
        object.__setattr__(self, "aspectos", dict(self.aspectos))
