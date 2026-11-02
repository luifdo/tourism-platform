"""Tipos de evento que publica el IAM (`contracts/events/`)."""

from app.domain.events.prestador_aprobado import PrestadorAprobado
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.events.usuario_suprimido import UsuarioSuprimido

TIPOS_PUBLICADOS: frozenset[str] = frozenset(
    evento.tipo for evento in (PrestadorAprobado, PrestadorSuspendido, UsuarioSuprimido)
)
