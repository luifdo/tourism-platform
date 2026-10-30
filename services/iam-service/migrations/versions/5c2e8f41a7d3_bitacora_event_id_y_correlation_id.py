"""bitacora: event_id y correlation_id

Revision ID: 5c2e8f41a7d3
Revises: 077dd88b0ea8
Create Date: 2026-10-29 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c2e8f41a7d3"
down_revision: str | None = "077dd88b0ea8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADD COLUMN no dispara los triggers de inmutabilidad (son FOR EACH ROW sobre UPDATE).
    # C-04: idempotencia de auditoria.registrada en la base; nulo en las filas propias del IAM.
    op.add_column("bitacora_auditoria", sa.Column("event_id", sa.UUID(), nullable=True))
    op.create_unique_constraint(
        op.f("uq_bitacora_auditoria_event_id"), "bitacora_auditoria", ["event_id"]
    )
    # C-05: X-Correlation-ID de la petición o del sobre del evento.
    op.add_column(
        "bitacora_auditoria", sa.Column("correlation_id", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("bitacora_auditoria", "correlation_id")
    op.drop_constraint(op.f("uq_bitacora_auditoria_event_id"), "bitacora_auditoria", type_="unique")
    op.drop_column("bitacora_auditoria", "event_id")
