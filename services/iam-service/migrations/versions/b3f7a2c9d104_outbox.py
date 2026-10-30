"""outbox

Revision ID: b3f7a2c9d104
Revises: 9a41d6c3e2b8
Create Date: 2026-10-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3f7a2c9d104"
down_revision: str | None = "9a41d6c3e2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # C-09 (ADR-008): el evento se guarda con el cambio y el relay del worker lo publica.
    # Mismo esquema que el outbox de catalog.
    op.create_table(
        "outbox",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("sobre", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_outbox")),
    )
    op.create_index(
        "ix_outbox_pendientes",
        "outbox",
        ["creado_en"],
        postgresql_where=sa.text("publicado_en IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_pendientes", table_name="outbox")
    op.drop_table("outbox")
