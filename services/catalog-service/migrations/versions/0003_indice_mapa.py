"""Índice para recortar servicios por la vista del mapa.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-18

La vista de Leaflet es un rectángulo en lon/lat. Con `geometry` el filtro `&&` contra
ST_MakeEnvelope es exacto en esos grados; con `geography` los bordes serían geodésicos y
podrían dejar fuera puntos pegados al borde. El índice de `ubicacion` (geography) sigue
sirviendo a ST_DWithin y ST_Distance en metros.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_servicio_ubicacion_plana ON atractivo_servicio "
        "USING gist ((ubicacion::geometry)) WHERE activo"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_servicio_ubicacion_plana")
