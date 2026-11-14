"""usuario: idioma

Revision ID: 9a41d6c3e2b8
Revises: 5c2e8f41a7d3
Create Date: 2026-10-29 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a41d6c3e2b8"
down_revision: str | None = "5c2e8f41a7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # C-06: idioma de los correos. Las cuentas existentes quedan en español.
    op.add_column(
        "usuario",
        sa.Column("idioma", sa.String(length=2), server_default=sa.text("'es'"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_usuario_idioma_valido"), "usuario", "idioma IN ('es', 'en')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_usuario_idioma_valido"), "usuario", type_="check")
    op.drop_column("usuario", "idioma")
