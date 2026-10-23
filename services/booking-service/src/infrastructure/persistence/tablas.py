"""Tablas de booking_db con SQLAlchemy Core (sin ORM).

Core define las tablas en Python, pero las consultas se escriben casi como SQL
(`select(...).with_for_update()`): se ve exactamente qué se lee y qué se bloquea.
Los repositorios (paso 5.2) convierten cada fila en un objeto del dominio y viceversa.

Las restricciones (`CHECK`, `UNIQUE`, llaves foráneas) son la **segunda barrera**: si un
día el código fallara, Postgres rechaza el dato inválido en vez de guardarlo.
Modelo completo: Plan de sprints, sección "Modelo de base de datos (booking_db)".
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from domain.reserva import Actor, EstadoReserva

# Nombres fijos para las restricciones: Alembic los necesita para poder modificarlas después.
CONVENCION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
}
metadata = MetaData(naming_convention=CONVENCION)

DINERO = Numeric(12, 2)  # COP, exacto (nunca float)


def _instante() -> DateTime:
    return DateTime(timezone=True)  # timestamptz: el instante, sin ambigüedad de zona


def _en(valores) -> str:
    return ", ".join(f"'{v.value}'" for v in valores)


ACTIVOS = _en([EstadoReserva.SOLICITADA, EstadoReserva.CONFIRMADA])


# ---------- servicio_ref: proyección del catálogo (la escribe solo el consumidor de servicio.publicado) ----------

servicio_ref = Table(
    "servicio_ref",
    metadata,
    Column("servicio_id", UUID(as_uuid=True), primary_key=True),
    Column("prestador_id", UUID(as_uuid=True), nullable=False, comment="Perfil del prestador en el catálogo; va en los eventos"),
    Column("prestador_usuario_id", UUID(as_uuid=True), nullable=False, comment="Usuario del prestador en iam (X-Usuario-Id); autoriza"),
    Column("capacidad_aforo_diario", Integer, nullable=False),
    Column("tarifa_base", DINERO, nullable=False),
    Column("activo", Boolean, nullable=False),
    Column("version", Integer, nullable=False, comment="Versión del servicio en el catálogo; solo se aplica una mayor"),
    Column("actualizado_en", _instante(), nullable=False, server_default=func.now()),
    CheckConstraint("capacidad_aforo_diario >= 1", name="aforo_positivo"),
    CheckConstraint("tarifa_base >= 0", name="tarifa_base_no_negativa"),
    CheckConstraint("version >= 1", name="version_positiva"),
    Index(None, "prestador_usuario_id"),
)


# ---------- disponibilidad_cupo: cupos de un servicio en un día ----------

disponibilidad_cupo = Table(
    "disponibilidad_cupo",
    metadata,
    # La llave es el propio (servicio, día): es como el dominio identifica la fila y es lo que bloquea FOR UPDATE.
    Column("servicio_id", UUID(as_uuid=True), ForeignKey("servicio_ref.servicio_id"), primary_key=True),
    Column("fecha", Date, primary_key=True, comment="Día de operación en Bogotá"),
    Column("cupos_totales", Integer, nullable=False),
    Column("cupos_disponibles", Integer, nullable=False),
    Column("tarifa_dia", DINERO, nullable=True, comment="Nula = tarifa_base de servicio_ref"),
    Column("version", Integer, nullable=False, server_default="1", comment="Ediciones del prestador (ETag / If-Match)"),
    Column("secuencia", Integer, nullable=False, server_default="1", comment="Cada cambio; version del evento disponibilidad.actualizada"),
    Column("creado_en", _instante(), nullable=False, server_default=func.now()),
    Column("actualizado_en", _instante(), nullable=False, server_default=func.now()),
    CheckConstraint("cupos_totales >= 0", name="totales_no_negativos"),
    # Segunda barrera contra la sobreventa: nunca menos de 0 ni más que el total.
    CheckConstraint("cupos_disponibles BETWEEN 0 AND cupos_totales", name="disponibles_en_rango"),
    CheckConstraint("tarifa_dia IS NULL OR tarifa_dia >= 0", name="tarifa_dia_no_negativa"),
    CheckConstraint("version >= 1 AND secuencia >= 1", name="contadores_positivos"),
)


# ---------- solicitud_reserva: cada reserva y su estado ----------

solicitud_reserva = Table(
    "solicitud_reserva",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, comment="reserva_id en los eventos"),
    Column("turista_id", UUID(as_uuid=True), nullable=False),
    Column("servicio_id", UUID(as_uuid=True), nullable=False),
    Column("prestador_id", UUID(as_uuid=True), nullable=False, comment="Perfil; copiado de servicio_ref al solicitar"),
    Column("prestador_usuario_id", UUID(as_uuid=True), nullable=False, comment="Usuario; copiado de servicio_ref al solicitar"),
    Column("fecha_reserva", Date, nullable=False),
    Column("numero_personas", Integer, nullable=False),
    Column("estado", String(12), nullable=False),
    Column("expira_en", _instante(), nullable=True, comment="Plazo del prestador; solo en SOLICITADA"),
    Column("motivo", String(500), nullable=True),
    Column("cancelada_por", String(10), nullable=True),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("creado_en", _instante(), nullable=False),
    Column("actualizado_en", _instante(), nullable=False),
    # Toda reserva apunta a un día abierto, y un día con reservas no se puede borrar.
    ForeignKeyConstraint(
        ["servicio_id", "fecha_reserva"],
        ["disponibilidad_cupo.servicio_id", "disponibilidad_cupo.fecha"],
        name="fk_solicitud_reserva_dia",
    ),
    CheckConstraint("numero_personas >= 1", name="personas_positivas"),
    CheckConstraint(f"estado IN ({_en(EstadoReserva)})", name="estado_valido"),
    CheckConstraint("(estado = 'SOLICITADA') = (expira_en IS NOT NULL)", name="plazo_solo_en_solicitada"),
    CheckConstraint("estado <> 'RECHAZADA' OR motivo IS NOT NULL", name="rechazo_con_motivo"),
    CheckConstraint("(estado = 'CANCELADA') = (cancelada_por IS NOT NULL)", name="cancelada_por_solo_en_cancelada"),
    CheckConstraint(f"cancelada_por IS NULL OR cancelada_por IN ({_en(Actor)})", name="cancelada_por_valido"),
    CheckConstraint("version >= 1", name="version_positiva"),
    # R6 en la base: una sola reserva activa por turista, servicio y fecha.
    Index(
        "uq_solicitud_reserva_activa",
        "turista_id", "servicio_id", "fecha_reserva",
        unique=True,
        postgresql_where=text(f"estado IN ({ACTIVOS})"),
    ),
    Index("ix_solicitud_reserva_historial", "turista_id", text("creado_en DESC")),  # UC13
    Index("ix_solicitud_reserva_panel", "prestador_usuario_id", "estado", "expira_en"),  # UC20
    Index("ix_solicitud_reserva_por_expirar", "expira_en", postgresql_where=text("estado = 'SOLICITADA'")),
    Index("ix_solicitud_reserva_por_finalizar", "fecha_reserva", postgresql_where=text("estado = 'CONFIRMADA'")),
)


# ---------- evento_outbox: eventos guardados en la misma transacción, publicados después (paso 5.3) ----------

evento_outbox = Table(
    "evento_outbox",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, comment="Es el event_id del sobre: así los consumidores descartan duplicados"),
    Column("tipo", String(60), nullable=False, comment="Routing key, p. ej. reserva.confirmada"),
    Column("sobre", JSONB, nullable=False, comment="Mensaje completo según envelope.v1.json"),
    Column("creado_en", _instante(), nullable=False, server_default=func.now()),
    Column("publicado_en", _instante(), nullable=True, comment="Nulo = pendiente de publicar"),
    Column("intentos", Integer, nullable=False, server_default="0"),
    Column("ultimo_error", Text, nullable=True),
    CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
    # El publicador lee los pendientes en orden de llegada.
    Index("ix_evento_outbox_pendientes", "creado_en", postgresql_where=text("publicado_en IS NULL")),
)
