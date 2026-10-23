"""Puertos: interfaces que la aplicación necesita y la infraestructura implementa."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol, Self
from uuid import UUID

from domain.disponibilidad import DisponibilidadCupo
from domain.eventos import EventoDominio
from domain.reserva import EstadoReserva, Reserva
from domain.servicio import ServicioRef


@dataclass(frozen=True)
class FiltroReservas:
    turista_id: UUID | None = None
    prestador_usuario_id: UUID | None = None
    servicio_id: UUID | None = None
    estado: EstadoReserva | None = None
    desde: date | None = None
    hasta: date | None = None
    orden: str = "recientes"  # "recientes" o "expira_en"


class RepositorioServicios(Protocol):
    """Proyección `servicio_ref`, alimentada por `servicio.publicado.v1`."""

    async def leer(self, servicio_id: UUID) -> ServicioRef | None:
        """Lectura sin bloqueo."""

    async def guardar_si_mas_nuevo(self, servicio: ServicioRef) -> bool:
        """Guarda el servicio solo si no existe o si su versión es mayor que la guardada, en un
        solo paso atómico (sin leer antes). Devuelve si lo guardó."""


class RepositorioReservas(Protocol):
    """Dos formas de leer una reserva, según para qué:

    * `obtener_para_cambiar`: antes de cambiar su estado. Bloquea la fila hasta el fin de la
      transacción (SELECT ... FOR UPDATE), así dos cambios a la vez no se pisan.
    * `leer`: solo para mostrarla (un GET). No bloquea: no hace esperar a quien la está cambiando.
    """

    async def obtener_para_cambiar(self, reserva_id: UUID) -> Reserva | None: ...

    async def leer(self, reserva_id: UUID) -> Reserva | None: ...

    async def guardar(self, reserva: Reserva) -> None: ...

    async def existe_activa(
        self, turista_id: UUID, servicio_id: UUID, fecha: date, excluir: UUID | None = None
    ) -> bool: ...

    async def listar(
        self, filtro: FiltroReservas, pagina: int, tamano: int
    ) -> tuple[list[Reserva], int]: ...

    async def solicitudes_vencidas(self, ahora: datetime, limite: int) -> list[Reserva]:
        """SOLICITADA con expira_en <= ahora, bloqueadas (FOR UPDATE SKIP LOCKED)."""

    async def por_finalizar(self, hoy: date, limite: int) -> list[Reserva]:
        """CONFIRMADA con fecha_reserva < hoy, bloqueadas (FOR UPDATE SKIP LOCKED)."""


class RepositorioDisponibilidad(Protocol):
    async def obtener_para_cambiar(self, servicio_id: UUID, fecha: date) -> DisponibilidadCupo | None:
        """Lee y bloquea la fila del día (SELECT ... FOR UPDATE): siempre precede a un cambio de cupos."""

    async def guardar(self, dia: DisponibilidadCupo) -> None:
        """Crea o actualiza el día. Si otra petición acaba de crear el mismo día nuevo, lanza
        `DiaExistente` en vez de pisarlo."""

    async def rango(self, servicio_id: UUID, desde: date, hasta: date) -> list[DisponibilidadCupo]:
        """Lectura sin bloqueo (consulta pública y calendario del prestador)."""


class UnidadDeTrabajo(Protocol):
    servicios: RepositorioServicios
    reservas: RepositorioReservas
    disponibilidad: RepositorioDisponibilidad

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *exc: object) -> None:
        """Si no hubo commit, deshace."""

    async def commit(self) -> None: ...


class FabricaUnidadDeTrabajo(Protocol):
    def __call__(self) -> UnidadDeTrabajo: ...


class PublicadorEventos(Protocol):
    async def publicar(self, eventos: list[EventoDominio], correlation_id: str | None) -> None: ...


class AlmacenIdempotencia(Protocol):
    async def obtener(self, clave: str) -> Any | None: ...

    async def guardar(self, clave: str, respuesta: Any) -> None: ...


class Reloj(Protocol):
    def ahora(self) -> datetime: ...
