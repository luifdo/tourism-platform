"""Conteo diario de intenciones de visita ("Cómo llegar") por servicio.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-24

Solo se guarda el conteo por servicio y día: quién lo pidió no se guarda en la base (el
descarte de repetidos usa un hash del IP con sal diaria en Valkey, durante 24 h). Es un
indicador aparte del índice de saturación. Sin llave foránea, como las proyecciones.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE intencion_visita_dia (
            servicio_id uuid NOT NULL,
            fecha       date NOT NULL,
            conteo      integer NOT NULL CHECK (conteo >= 1),
            PRIMARY KEY (servicio_id, fecha)
        )
        """
    )
    op.execute("CREATE INDEX ix_intencion_fecha ON intencion_visita_dia (fecha)")


def downgrade() -> None:
    op.execute("DROP TABLE intencion_visita_dia")
