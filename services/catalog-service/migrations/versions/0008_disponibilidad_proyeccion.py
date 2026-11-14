"""Proyección de la disponibilidad de booking por servicio y día.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-23

catalog filtra la búsqueda y el mapa por fecha y personas con esta tabla, alimentada por
`disponibilidad.actualizada` (Plan §4.1: solo el Módulo 5 llama a otros servicios). Sin
llaves foráneas, como las demás proyecciones: un evento fuera de orden nunca bloquea al
consumidor. La llave primaria (servicio, fecha) sirve al filtro de la búsqueda.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE disponibilidad_proyeccion (
            servicio_id       uuid NOT NULL,
            fecha             date NOT NULL,
            cupos_totales     integer NOT NULL CHECK (cupos_totales >= 0),
            cupos_disponibles integer NOT NULL
                CHECK (cupos_disponibles BETWEEN 0 AND cupos_totales),
            version           integer NOT NULL CHECK (version >= 1),
            actualizado_en    timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (servicio_id, fecha)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE disponibilidad_proyeccion")
