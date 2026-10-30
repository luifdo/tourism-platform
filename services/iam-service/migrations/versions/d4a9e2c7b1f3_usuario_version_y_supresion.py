"""usuario: version (RNF-13) y datos_suprimidos_en (C-10, C-27)

Revision ID: d4a9e2c7b1f3
Revises: c8e4b1f6a920
Create Date: 2026-10-30 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a9e2c7b1f3"
down_revision: str | None = "c8e4b1f6a920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "usuario", sa.Column("datos_suprimidos_en", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("usuario", "datos_suprimidos_en")
    op.drop_column("usuario", "version")
