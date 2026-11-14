"""documentos de verificacion: vigente, tipo y tamano; razon_social

Revision ID: c8e4b1f6a920
Revises: b3f7a2c9d104
Create Date: 2026-10-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e4b1f6a920"
down_revision: str | None = "b3f7a2c9d104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # C-07: razón social del RUT.
    op.add_column("usuario", sa.Column("razon_social", sa.String(length=200), nullable=True))
    # C-30. La tabla no se usó antes del bloque 5 (C-02): las columnas nuevas pueden ser
    # NOT NULL sin valor por defecto.
    op.add_column(
        "documento_verificacion",
        sa.Column("tipo_contenido", sa.String(length=50), nullable=False),
    )
    op.add_column("documento_verificacion", sa.Column("tamano_bytes", sa.Integer(), nullable=False))
    op.add_column(
        "documento_verificacion",
        sa.Column("vigente", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index(
        "uq_documento_verificacion_vigente",
        "documento_verificacion",
        ["usuario_id", "tipo_documento"],
        unique=True,
        postgresql_where=sa.text("vigente"),
    )


def downgrade() -> None:
    op.drop_index("uq_documento_verificacion_vigente", table_name="documento_verificacion")
    op.drop_column("documento_verificacion", "vigente")
    op.drop_column("documento_verificacion", "tamano_bytes")
    op.drop_column("documento_verificacion", "tipo_contenido")
    op.drop_column("usuario", "razon_social")
