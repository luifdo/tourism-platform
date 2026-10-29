"""Momento del último evento de iam aplicado a cada perfil de prestador.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23

Un reintento del consumidor puede traer un `prestador.aprobado` viejo después de un
`prestador.suspendido` nuevo. Con `estado_iam_en` (el `occurred_at` del último evento
aplicado) el consumidor ignora los eventos más viejos y no reactiva a un suspendido.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE prestador_perfil ADD COLUMN estado_iam_en timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE prestador_perfil DROP COLUMN estado_iam_en")
