"""Esquema inicial de booking_db: servicio_ref, disponibilidad_cupo, solicitud_reserva y evento_outbox.

Revisión: 0001
Anterior: (ninguna)
Creada: 2026-10-23

Generada con `alembic revision --autogenerate` a partir de infrastructure/persistence/tablas.py
y revisada a mano (orden por dependencias y downgrade simplificado). Las pruebas de
integración comprueban que la base migrada coincide con tablas.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. servicio_ref: proyección del catálogo. Va primero porque disponibilidad_cupo la referencia.
    op.create_table(
        "servicio_ref",
        sa.Column("servicio_id", sa.UUID(), nullable=False),
        sa.Column("prestador_id", sa.UUID(), nullable=False, comment="Perfil del prestador en el catálogo; va en los eventos"),
        sa.Column("prestador_usuario_id", sa.UUID(), nullable=False, comment="Usuario del prestador en iam (X-Usuario-Id); autoriza"),
        sa.Column("capacidad_aforo_diario", sa.Integer(), nullable=False),
        sa.Column("tarifa_base", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, comment="Versión del servicio en el catálogo; solo se aplica una mayor"),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("capacidad_aforo_diario >= 1", name=op.f("ck_servicio_ref_aforo_positivo")),
        sa.CheckConstraint("tarifa_base >= 0", name=op.f("ck_servicio_ref_tarifa_base_no_negativa")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_servicio_ref_version_positiva")),
        sa.PrimaryKeyConstraint("servicio_id", name=op.f("pk_servicio_ref")),
    )
    op.create_index(op.f("ix_servicio_ref_prestador_usuario_id"), "servicio_ref", ["prestador_usuario_id"], unique=False)

    # 2. disponibilidad_cupo: cupos de un servicio en un día. La llave (servicio_id, fecha) es lo que bloquea FOR UPDATE.
    op.create_table(
        "disponibilidad_cupo",
        sa.Column("servicio_id", sa.UUID(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False, comment="Día de operación en Bogotá"),
        sa.Column("cupos_totales", sa.Integer(), nullable=False),
        sa.Column("cupos_disponibles", sa.Integer(), nullable=False),
        sa.Column("tarifa_dia", sa.Numeric(precision=12, scale=2), nullable=True, comment="Nula = tarifa_base de servicio_ref"),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False, comment="Ediciones del prestador (ETag / If-Match)"),
        sa.Column("secuencia", sa.Integer(), server_default="1", nullable=False, comment="Cada cambio; version del evento disponibilidad.actualizada"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Segunda barrera contra la sobreventa.
        sa.CheckConstraint("cupos_disponibles BETWEEN 0 AND cupos_totales", name=op.f("ck_disponibilidad_cupo_disponibles_en_rango")),
        sa.CheckConstraint("cupos_totales >= 0", name=op.f("ck_disponibilidad_cupo_totales_no_negativos")),
        sa.CheckConstraint("tarifa_dia IS NULL OR tarifa_dia >= 0", name=op.f("ck_disponibilidad_cupo_tarifa_dia_no_negativa")),
        sa.CheckConstraint("version >= 1 AND secuencia >= 1", name=op.f("ck_disponibilidad_cupo_contadores_positivos")),
        sa.ForeignKeyConstraint(["servicio_id"], ["servicio_ref.servicio_id"], name=op.f("fk_disponibilidad_cupo_servicio_id")),
        sa.PrimaryKeyConstraint("servicio_id", "fecha", name=op.f("pk_disponibilidad_cupo")),
    )

    # 3. solicitud_reserva: cada reserva y su estado. Apunta al día reservado con una llave compuesta.
    op.create_table(
        "solicitud_reserva",
        sa.Column("id", sa.UUID(), nullable=False, comment="reserva_id en los eventos"),
        sa.Column("turista_id", sa.UUID(), nullable=False),
        sa.Column("servicio_id", sa.UUID(), nullable=False),
        sa.Column("prestador_id", sa.UUID(), nullable=False, comment="Perfil; copiado de servicio_ref al solicitar"),
        sa.Column("prestador_usuario_id", sa.UUID(), nullable=False, comment="Usuario; copiado de servicio_ref al solicitar"),
        sa.Column("fecha_reserva", sa.Date(), nullable=False),
        sa.Column("numero_personas", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=12), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=True, comment="Plazo del prestador; solo en SOLICITADA"),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("cancelada_por", sa.String(length=10), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("numero_personas >= 1", name=op.f("ck_solicitud_reserva_personas_positivas")),
        sa.CheckConstraint(
            "estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA')",
            name=op.f("ck_solicitud_reserva_estado_valido"),
        ),
        sa.CheckConstraint("(estado = 'SOLICITADA') = (expira_en IS NOT NULL)", name=op.f("ck_solicitud_reserva_plazo_solo_en_solicitada")),
        sa.CheckConstraint("estado <> 'RECHAZADA' OR motivo IS NOT NULL", name=op.f("ck_solicitud_reserva_rechazo_con_motivo")),
        sa.CheckConstraint("(estado = 'CANCELADA') = (cancelada_por IS NOT NULL)", name=op.f("ck_solicitud_reserva_cancelada_por_solo_en_cancelada")),
        sa.CheckConstraint("cancelada_por IS NULL OR cancelada_por IN ('Turista', 'Prestador')", name=op.f("ck_solicitud_reserva_cancelada_por_valido")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_solicitud_reserva_version_positiva")),
        sa.ForeignKeyConstraint(
            ["servicio_id", "fecha_reserva"],
            ["disponibilidad_cupo.servicio_id", "disponibilidad_cupo.fecha"],
            name="fk_solicitud_reserva_dia",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solicitud_reserva")),
    )
    # R6: una sola reserva activa por turista, servicio y fecha.
    op.create_index(
        "uq_solicitud_reserva_activa", "solicitud_reserva", ["turista_id", "servicio_id", "fecha_reserva"],
        unique=True, postgresql_where=sa.text("estado IN ('SOLICITADA', 'CONFIRMADA')"),
    )
    op.create_index("ix_solicitud_reserva_historial", "solicitud_reserva", ["turista_id", sa.literal_column("creado_en DESC")], unique=False)
    op.create_index("ix_solicitud_reserva_panel", "solicitud_reserva", ["prestador_usuario_id", "estado", "expira_en"], unique=False)
    op.create_index(
        "ix_solicitud_reserva_por_expirar", "solicitud_reserva", ["expira_en"],
        unique=False, postgresql_where=sa.text("estado = 'SOLICITADA'"),
    )
    op.create_index(
        "ix_solicitud_reserva_por_finalizar", "solicitud_reserva", ["fecha_reserva"],
        unique=False, postgresql_where=sa.text("estado = 'CONFIRMADA'"),
    )

    # 4. evento_outbox: eventos guardados en la misma transacción que el cambio (paso 5.3).
    op.create_table(
        "evento_outbox",
        sa.Column("id", sa.UUID(), nullable=False, comment="Es el event_id del sobre: así los consumidores descartan duplicados"),
        sa.Column("tipo", sa.String(length=60), nullable=False, comment="Routing key, p. ej. reserva.confirmada"),
        sa.Column("sobre", postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment="Mensaje completo según envelope.v1.json"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True, comment="Nulo = pendiente de publicar"),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.CheckConstraint("intentos >= 0", name=op.f("ck_evento_outbox_intentos_no_negativos")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento_outbox")),
    )
    op.create_index("ix_evento_outbox_pendientes", "evento_outbox", ["creado_en"], unique=False, postgresql_where=sa.text("publicado_en IS NULL"))


def downgrade() -> None:
    # En orden inverso a las dependencias. Al borrar una tabla, Postgres borra también sus índices.
    op.drop_table("evento_outbox")
    op.drop_table("solicitud_reserva")
    op.drop_table("disponibilidad_cupo")
    op.drop_table("servicio_ref")
