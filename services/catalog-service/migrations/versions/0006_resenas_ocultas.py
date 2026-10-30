"""Reseñas ocultas por moderación y momento del último evento de cada reseña.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23

* `visible`: una reseña que el Administrador oculta (`resena.ocultada`, UC29) deja de contar
  en la calificación promedio; si se vuelve a publicar, vuelve a contar.
* `ultimo_evento_en`: `occurred_at` del último evento aplicado, para ignorar uno más viejo que
  llegue tarde por un reintento. Nula en las filas anteriores a esta migración.
* El índice cubre el promedio por servicio solo con las reseñas visibles.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE calificacion_resena
            ADD COLUMN visible boolean NOT NULL DEFAULT true,
            ADD COLUMN ultimo_evento_en timestamptz
        """
    )
    op.execute("DROP INDEX ix_calificacion_servicio")
    op.execute(
        "CREATE INDEX ix_calificacion_servicio ON calificacion_resena (servicio_id)"
        " INCLUDE (puntuacion) WHERE visible"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_calificacion_servicio")
    op.execute("CREATE INDEX ix_calificacion_servicio ON calificacion_resena (servicio_id)")
    op.execute(
        "ALTER TABLE calificacion_resena DROP COLUMN ultimo_evento_en, DROP COLUMN visible"
    )
