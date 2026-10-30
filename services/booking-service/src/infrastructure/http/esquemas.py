"""Esquemas de entrada y salida de la API (contracts/openapi/booking.yaml)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.disponibilidad import DisponibilidadCupo
from domain.reserva import Actor, EstadoReserva, Reserva


class Error(BaseModel):
    error: str
    message: str
    correlation_id: str


# ---------- Entrada ----------

class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SolicitudReservaCrear(_Entrada):
    servicio_id: UUID
    fecha_reserva: date = Field(description="A partir de mañana.")
    numero_personas: int = Field(ge=1)


class SolicitudReservaModificar(_Entrada):
    fecha_reserva: date | None = None
    numero_personas: int | None = Field(default=None, ge=1)


class Motivo(_Entrada):
    motivo: str | None = Field(default=None, max_length=500, description="Obligatorio cuando cancela el prestador.")


class MotivoObligatorio(_Entrada):
    motivo: str = Field(min_length=3, max_length=500)


class DiaCalendarioGuardar(_Entrada):
    cupos_totales: int = Field(ge=0, description="No menor que lo ya reservado ni mayor que el aforo oficial.")
    tarifa_dia: Decimal | None = Field(default=None, ge=0)


class RangoCalendario(_Entrada):
    desde: date
    hasta: date = Field(description="Máximo 366 días después de `desde`.")
    dias_semana: list[int] | None = Field(default=None, description="1 = lunes … 7 = domingo. Si se omite, todos.")
    cupos_totales: int = Field(ge=1)
    tarifa_dia: Decimal | None = Field(default=None, ge=0)


# ---------- Salida ----------

class ReservaSalida(BaseModel):
    id: UUID
    servicio_id: UUID
    turista_id: UUID
    prestador_id: UUID = Field(description="Id del perfil del prestador en el catálogo (el mismo de los eventos).")
    fecha_reserva: date
    numero_personas: int
    estado: EstadoReserva
    expira_en: datetime | None
    motivo: str | None
    cancelada_por: Actor | None
    version: int
    creado_en: datetime
    actualizado_en: datetime

    @classmethod
    def de(cls, r: Reserva) -> "ReservaSalida":
        return cls(
            id=r.id, servicio_id=r.servicio_id, turista_id=r.turista_id, prestador_id=r.prestador_id,
            fecha_reserva=r.fecha_reserva, numero_personas=r.numero_personas, estado=r.estado,
            expira_en=r.expira_en, motivo=r.motivo, cancelada_por=r.cancelada_por, version=r.version,
            creado_en=r.creado_en, actualizado_en=r.actualizado_en,
        )


class PaginaReservas(BaseModel):
    items: list[ReservaSalida]
    pagina: int
    tamano: int
    total: int


class DiaDisponible(BaseModel):
    fecha: date
    cupos_disponibles: int
    tarifa_dia: Decimal | None


class Disponibilidad(BaseModel):
    servicio_id: UUID
    dias: list[DiaDisponible]


class DiaCalendario(BaseModel):
    fecha: date
    cupos_totales: int
    cupos_disponibles: int
    cupos_reservados: int
    tarifa_dia: Decimal | None
    version: int

    @classmethod
    def de(cls, d: DisponibilidadCupo) -> "DiaCalendario":
        return cls(
            fecha=d.fecha, cupos_totales=d.cupos_totales, cupos_disponibles=d.cupos_disponibles,
            cupos_reservados=d.cupos_reservados, tarifa_dia=d.tarifa_dia, version=d.version,
        )


class Calendario(BaseModel):
    servicio_id: UUID
    dias: list[DiaCalendario]


class ResultadoRango(BaseModel):
    creados: list[date]
    omitidos: list[date] = Field(description="Días que ya existían.")
