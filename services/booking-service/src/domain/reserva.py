"""Reserva y su máquina de estados (Guía §4, SRS §3.6.1).

Cada transición deja un `EventoDominio` en `reserva.eventos`; la capa de aplicación
los guarda en el outbox en la misma transacción. Los cupos los mueve el caso de uso sobre
`DisponibilidadCupo`, porque viven en otra fila.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from domain import reglas
from domain.errores import FueraDePlazo, PlazoVencido, TransicionInvalida, Validacion
from domain.eventos import EventoDominio

if TYPE_CHECKING:
    from domain.servicio import ServicioRef

MOTIVO_PLAZO_VENCIDO = "Plazo de respuesta vencido"
MOTIVO_MAX = 500


class EstadoReserva(StrEnum):
    SOLICITADA = "SOLICITADA"
    CONFIRMADA = "CONFIRMADA"
    RECHAZADA = "RECHAZADA"
    CANCELADA = "CANCELADA"
    FINALIZADA = "FINALIZADA"


class Actor(StrEnum):
    TURISTA = "Turista"
    PRESTADOR = "Prestador"


ESTADOS_ACTIVOS = frozenset({EstadoReserva.SOLICITADA, EstadoReserva.CONFIRMADA})


@dataclass
class Reserva:
    id: UUID
    servicio_id: UUID
    turista_id: UUID
    prestador_id: UUID  # perfil del prestador; es el que viaja en los eventos
    prestador_usuario_id: UUID  # usuario del prestador en iam; sirve para autorizar
    fecha_reserva: date
    numero_personas: int
    estado: EstadoReserva
    expira_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime
    motivo: str | None = None
    cancelada_por: Actor | None = None
    version: int = 1
    eventos: list[EventoDominio] = field(default_factory=list, repr=False, compare=False)

    # ---------- Creación ----------

    @classmethod
    def solicitar(
        cls,
        servicio: "ServicioRef",
        turista_id: UUID,
        fecha_reserva: date,
        numero_personas: int,
        ahora: datetime,
        plazo_horas: int = reglas.PLAZO_RESPUESTA_HORAS,
    ) -> "Reserva":
        servicio.exigir_activo()
        _validar_personas(numero_personas)
        reglas.validar_fecha_solicitud(fecha_reserva, ahora)
        reserva = cls(
            id=uuid4(),
            servicio_id=servicio.servicio_id,
            turista_id=turista_id,
            prestador_id=servicio.prestador_id,
            prestador_usuario_id=servicio.prestador_usuario_id,
            fecha_reserva=fecha_reserva,
            numero_personas=numero_personas,
            estado=EstadoReserva.SOLICITADA,
            expira_en=reglas.calcular_expira_en(fecha_reserva, ahora, plazo_horas),
            creado_en=ahora,
            actualizado_en=ahora,
        )
        reserva._registrar("reserva.solicitada")
        return reserva

    # ---------- Transiciones ----------

    def modificar(
        self,
        ahora: datetime,
        fecha_reserva: date | None = None,
        numero_personas: int | None = None,
        plazo_horas: int = reglas.PLAZO_RESPUESTA_HORAS,
    ) -> None:
        """UC12: solo en SOLICITADA. Reinicia el plazo de respuesta."""
        self._exigir(EstadoReserva.SOLICITADA, "modificar")
        if fecha_reserva is None and numero_personas is None:
            raise Validacion("Indique la nueva fecha o el nuevo número de personas.")
        nueva_fecha = self.fecha_reserva if fecha_reserva is None else fecha_reserva
        nuevas_personas = self.numero_personas if numero_personas is None else numero_personas
        _validar_personas(nuevas_personas)
        reglas.validar_fecha_solicitud(nueva_fecha, ahora)

        fecha_anterior, personas_anterior = self.fecha_reserva, self.numero_personas
        self.fecha_reserva = nueva_fecha
        self.numero_personas = nuevas_personas
        self.expira_en = reglas.calcular_expira_en(nueva_fecha, ahora, plazo_horas)
        self._tocar(ahora)
        self._registrar(
            "reserva.modificada",
            fecha_anterior=fecha_anterior.isoformat(),
            numero_personas_anterior=personas_anterior,
            expira_en=self.expira_en.isoformat(),
        )

    def confirmar(self, ahora: datetime) -> None:
        self._exigir(EstadoReserva.SOLICITADA, "confirmar")
        if self._vencida(ahora):
            raise PlazoVencido("El plazo para responder esta solicitud ya venció.")
        self.estado = EstadoReserva.CONFIRMADA
        self.expira_en = None
        self._tocar(ahora)
        self._registrar("reserva.confirmada")

    def rechazar(self, motivo: str, ahora: datetime) -> None:
        self._exigir(EstadoReserva.SOLICITADA, "rechazar")
        self._cerrar_como_rechazada(_motivo_obligatorio(motivo), ahora)

    def expirar(self, ahora: datetime) -> None:
        """La ejecuta el CronJob `expirar-solicitudes`."""
        self._exigir(EstadoReserva.SOLICITADA, "expirar")
        if not self._vencida(ahora):
            raise TransicionInvalida("La solicitud todavía está dentro del plazo.")
        self._cerrar_como_rechazada(MOTIVO_PLAZO_VENCIDO, ahora)

    def cancelar(self, por: Actor, ahora: datetime, motivo: str | None = None) -> None:
        """Guía §4.3: turista en SOLICITADA siempre y en CONFIRMADA hasta el día anterior;
        prestador solo en CONFIRMADA (en SOLICITADA rechaza) y con motivo."""
        if por is Actor.PRESTADOR:
            self._exigir(EstadoReserva.CONFIRMADA, "cancelar")
            motivo = _motivo_obligatorio(motivo)
        else:
            if self.estado not in ESTADOS_ACTIVOS:
                raise self._transicion_invalida("cancelar")
            if (
                self.estado is EstadoReserva.CONFIRMADA
                and not reglas.turista_puede_cancelar_confirmada(self.fecha_reserva, ahora)
            ):
                raise FueraDePlazo(
                    "Las reservas confirmadas se cancelan hasta el día anterior; "
                    "contacte al prestador."
                )
            motivo = _motivo_opcional(motivo)
        self.estado = EstadoReserva.CANCELADA
        self.cancelada_por = por
        self.motivo = motivo
        self.expira_en = None
        self._tocar(ahora)
        extra: dict[str, Any] = {"cancelada_por": por.value}
        if motivo:
            extra["motivo"] = motivo
        self._registrar("reserva.cancelada", **extra)

    def finalizar(self, ahora: datetime) -> None:
        """La ejecuta el CronJob `finalizar-reservas`."""
        self._exigir(EstadoReserva.CONFIRMADA, "finalizar")
        if reglas.hoy_local(ahora) <= self.fecha_reserva:
            raise TransicionInvalida("La fecha de la reserva todavía no ha pasado.")
        self.estado = EstadoReserva.FINALIZADA
        self._tocar(ahora)
        self._registrar("reserva.finalizada")

    # ---------- Consultas ----------

    def extraer_eventos(self) -> list[EventoDominio]:
        eventos, self.eventos = self.eventos, []
        return eventos

    # ---------- Internos ----------

    def _cerrar_como_rechazada(self, motivo: str, ahora: datetime) -> None:
        self.estado = EstadoReserva.RECHAZADA
        self.motivo = motivo
        self.expira_en = None
        self._tocar(ahora)
        self._registrar("reserva.rechazada", motivo=motivo)

    def _vencida(self, ahora: datetime) -> bool:
        return self.expira_en is not None and ahora >= self.expira_en

    def _exigir(self, estado: EstadoReserva, accion: str) -> None:
        if self.estado is not estado:
            raise self._transicion_invalida(accion)

    def _transicion_invalida(self, accion: str) -> TransicionInvalida:
        return TransicionInvalida(f"No se puede {accion} una reserva en estado {self.estado}.")

    def _tocar(self, ahora: datetime) -> None:
        self.actualizado_en = ahora
        self.version += 1

    def _registrar(self, tipo: str, **extra: Any) -> None:
        payload: dict[str, Any] = {
            "reserva_id": str(self.id),
            "servicio_id": str(self.servicio_id),
            "turista_id": str(self.turista_id),
            "prestador_id": str(self.prestador_id),
            "fecha_reserva": self.fecha_reserva.isoformat(),
            "numero_personas": self.numero_personas,
            **extra,
        }
        self.eventos.append(EventoDominio(tipo, payload))


def _validar_personas(numero_personas: int) -> None:
    if numero_personas < 1:
        raise Validacion("El número de personas debe ser al menos 1.")


def _motivo_obligatorio(motivo: str | None) -> str:
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise Validacion("El motivo es obligatorio (mínimo 3 caracteres).")
    return _motivo_opcional(motivo)  # type: ignore[return-value]


def _motivo_opcional(motivo: str | None) -> str | None:
    motivo = (motivo or "").strip() or None
    if motivo and len(motivo) > MOTIVO_MAX:
        raise Validacion(f"El motivo admite máximo {MOTIVO_MAX} caracteres.")
    return motivo
