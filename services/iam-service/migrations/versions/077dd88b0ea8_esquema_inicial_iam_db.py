"""esquema inicial iam_db

Revision ID: 077dd88b0ea8
Revises:
Create Date: 2026-10-23 01:49:09.241487

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.config import get_settings

revision: str = "077dd88b0ea8"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los tipos se crean y eliminan aquí; las columnas los usan con create_type=False.
rol = postgresql.ENUM("Turista", "Prestador", "Entidad", "Admin", name="rol", create_type=False)
tipo_documento = postgresql.ENUM("RNT", "RUT", name="tipo_documento", create_type=False)
estado_documento = postgresql.ENUM(
    "Pendiente", "Aprobado", "Rechazado", name="estado_documento", create_type=False
)
resultado_auditoria = postgresql.ENUM(
    "Exito", "Denegado", "Error", name="resultado_auditoria", create_type=False
)
ENUMS = (rol, tipo_documento, estado_documento, resultado_auditoria)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUMS:
        enum_type.create(bind, checkfirst=False)

    op.create_table(
        "usuario",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("nombre_completo", sa.String(length=150), nullable=False),
        sa.Column("rol", rol, nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "email_verificado", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("habeas_data_aceptado", sa.Boolean(), nullable=False),
        sa.Column("habeas_data_aceptado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_usuario_email_minusculas")),
        sa.CheckConstraint(
            "habeas_data_aceptado = true", name=op.f("ck_usuario_habeas_data_aceptado")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
        sa.UniqueConstraint("email", name=op.f("uq_usuario_email")),
    )
    op.create_table(
        "bitacora_auditoria",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("accion", sa.String(length=50), nullable=False),
        sa.Column("resultado", resultado_auditoria, nullable=False),
        sa.Column(
            "servicio_origen", sa.String(length=50), server_default="iam-service", nullable=False
        ),
        sa.Column("ip_origen", postgresql.INET(), nullable=True),
        sa.Column(
            "detalles",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fecha", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_bitacora_auditoria_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bitacora_auditoria")),
    )
    op.create_index(op.f("ix_bitacora_auditoria_accion"), "bitacora_auditoria", ["accion"])
    op.create_index(op.f("ix_bitacora_auditoria_fecha"), "bitacora_auditoria", ["fecha"])
    op.create_index(op.f("ix_bitacora_auditoria_usuario_id"), "bitacora_auditoria", ["usuario_id"])
    op.create_table(
        "documento_verificacion",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("tipo_documento", tipo_documento, nullable=False),
        sa.Column("objeto_s3", sa.String(length=512), nullable=False),
        sa.Column("estado", estado_documento, server_default="Pendiente", nullable=False),
        sa.Column("motivo_rechazo", sa.Text(), nullable=True),
        sa.Column("revisado_por", sa.UUID(), nullable=True),
        sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fecha_subida",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["revisado_por"],
            ["usuario.id"],
            name=op.f("fk_documento_verificacion_revisado_por_usuario"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_documento_verificacion_usuario_id_usuario"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documento_verificacion")),
    )
    op.create_index(
        op.f("ix_documento_verificacion_usuario_id"), "documento_verificacion", ["usuario_id"]
    )

    # usuario.actualizado_en se refresca en cada UPDATE, también los que no pasan por el ORM.
    op.execute(
        """
        CREATE FUNCTION usuario_set_actualizado_en() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.actualizado_en := now();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER usuario_actualizado_en
        BEFORE UPDATE ON usuario
        FOR EACH ROW EXECUTE FUNCTION usuario_set_actualizado_en()
        """
    )

    # RNF-10: bitacora_auditoria es de solo inserción.
    op.execute(
        """
        CREATE FUNCTION bitacora_inmutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'bitacora_auditoria es de solo inserción (RNF-10)';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER bitacora_auditoria_inmutable
        BEFORE UPDATE OR DELETE ON bitacora_auditoria
        FOR EACH ROW EXECUTE FUNCTION bitacora_inmutable()
        """
    )
    # Los triggers FOR EACH ROW no se disparan con TRUNCATE.
    op.execute(
        """
        CREATE TRIGGER bitacora_auditoria_sin_truncate
        BEFORE TRUNCATE ON bitacora_auditoria
        FOR EACH STATEMENT EXECUTE FUNCTION bitacora_inmutable()
        """
    )
    # Defensa adicional en permisos. El REVOKE no tiene efecto sobre el dueño de la tabla ni
    # sobre un superusuario (en el compose de desarrollo iam_user es ambas cosas), así que la
    # protección real son los triggers de arriba.
    app_role = bind.dialect.identifier_preparer.quote(get_settings().db_app_role)
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON bitacora_auditoria FROM {app_role}")


def downgrade() -> None:
    op.execute("DROP TRIGGER bitacora_auditoria_sin_truncate ON bitacora_auditoria")
    op.execute("DROP TRIGGER bitacora_auditoria_inmutable ON bitacora_auditoria")
    op.execute("DROP FUNCTION bitacora_inmutable()")
    op.execute("DROP TRIGGER usuario_actualizado_en ON usuario")
    op.execute("DROP FUNCTION usuario_set_actualizado_en()")

    op.drop_index(op.f("ix_documento_verificacion_usuario_id"), table_name="documento_verificacion")
    op.drop_table("documento_verificacion")
    op.drop_index(op.f("ix_bitacora_auditoria_usuario_id"), table_name="bitacora_auditoria")
    op.drop_index(op.f("ix_bitacora_auditoria_fecha"), table_name="bitacora_auditoria")
    op.drop_index(op.f("ix_bitacora_auditoria_accion"), table_name="bitacora_auditoria")
    op.drop_table("bitacora_auditoria")
    op.drop_table("usuario")

    bind = op.get_bind()
    for enum_type in reversed(ENUMS):
        enum_type.drop(bind, checkfirst=False)
