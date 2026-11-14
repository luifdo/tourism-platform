"""Versión de las alertas oficiales para editarlas con `If-Match`.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-23

Varias personas de la Entidad pueden administrar las mismas alertas: editar exige la
versión que se leyó, igual que las zonas y los servicios. El índice sirve al panel de la
Entidad, que las lista de la más reciente a la más antigua.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alerta_oficial"
        " ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK (version >= 1)"
    )
    op.execute("CREATE INDEX ix_alerta_creada ON alerta_oficial (creada_en DESC, id)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_alerta_creada")
    op.execute("ALTER TABLE alerta_oficial DROP COLUMN version")
