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


class Outbox(Protocol):
    """Patrón outbox: los eventos se guardan en la misma transacción que el cambio que los
    produjo. Si el COMMIT sale, los eventos también; si no, no queda ninguno. Así nunca hay
    una reserva creada cuyo evento se perdió porque el pod se cayó justo después del COMMIT.
    Otro proceso (el relay) los publica en RabbitMQ después."""

    async def agregar(self, eventos: list[EventoDominio], correlation_id: str | None) -> None: ...


class UnidadDeTrabajo(Protocol):
    servicios: RepositorioServicios
    reservas: RepositorioReservas
    disponibilidad: RepositorioDisponibilidad
    outbox: Outbox

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *exc: object) -> None:
        """Si no hubo commit, deshace."""

    async def commit(self) -> None: ...


class FabricaUnidadDeTrabajo(Protocol):
    def __call__(self) -> UnidadDeTrabajo: ...


@dataclass(frozen=True)
class RespuestaGuardada:
    """La primera respuesta exitosa a una `Idempotency-Key`; un reintento la recibe tal cual."""

    estado: int
    cuerpo: bytes
    headers: dict[str, str]


class AlmacenIdempotencia(Protocol):
    """Guía §6.3. La clave pasa por dos estados: *en proceso* (reservada por la primera
    petición mientras corre) y *respondida* (con la respuesta guardada durante 48 h)."""

    async def reservar(self, clave: str) -> bool:
        """Marca la clave en proceso solo si no existía (atómico). False: otra petición ya la tiene."""
        ...

    async def obtener(self, clave: str) -> RespuestaGuardada | None:
        """La respuesta guardada; None si la clave no existe o sigue en proceso."""
        ...

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None: ...

    async def liberar(self, clave: str) -> None:
        """Borra la marca si la operación falló, para que un reintento la ejecute de nuevo."""
        ...


class Reloj(Protocol):
    def ahora(self) -> datetime: ...
