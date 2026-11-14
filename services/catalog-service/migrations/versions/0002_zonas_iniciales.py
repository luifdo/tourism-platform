"""Lista inicial de zonas turísticas de Santa Marta.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18

Los polígonos son rectángulos APROXIMADOS que no se superponen, pensados para arrancar el
prototipo. La Entidad de Gestión los corrige, agrega o desactiva desde la API (PUT /zonas).
Si dos zonas llegaran a cubrir el mismo punto, el servicio queda en la de menor área.
"""

import json
from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# codigo, nombre es, nombre en, (min_lon, min_lat, max_lon, max_lat)
ZONAS = [
    (
        "centro-historico",
        "Centro Histórico",
        "Historic Center",
        (-74.2160, 11.2330, -74.1960, 11.2500),
    ),
    ("el-rodadero", "El Rodadero", "El Rodadero", (-74.2400, 11.1950, -74.2200, 11.2150)),
    ("taganga", "Taganga", "Taganga", (-74.2000, 11.2560, -74.1820, 11.2760)),
    ("bahia-concha", "Bahía Concha", "Concha Bay", (-74.1600, 11.2880, -74.1350, 11.3080)),
    ("minca", "Minca", "Minca", (-74.1350, 11.1300, -74.1000, 11.1600)),
    (
        "parque-tayrona",
        "Parque Nacional Natural Tayrona",
        "Tayrona National Natural Park",
        (-74.1000, 11.2500, -73.9000, 11.3500),
    ),
]


def _id(codigo: str) -> str:
    # Id estable por código, para que todos los entornos tengan los mismos identificadores.
    return str(uuid5(NAMESPACE_URL, f"turismo-santa-marta/zona/{codigo}"))


def _rectangulo(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    anillo = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]
    return json.dumps({"type": "Polygon", "coordinates": [anillo]})


def upgrade() -> None:
    insertar = sa.text(
        """
        INSERT INTO zona (id, codigo, nombre, poligono)
        VALUES (
            CAST(:id AS uuid), :codigo, CAST(:nombre AS jsonb),
            ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:poligono), 4326))
        )
        """
    )
    for codigo, nombre_es, nombre_en, caja in ZONAS:
        op.get_bind().execute(
            insertar,
            {
                "id": _id(codigo),
                "codigo": codigo,
                "nombre": json.dumps({"es": nombre_es, "en": nombre_en}),
                "poligono": _rectangulo(*caja),
            },
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM zona WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [_id(codigo) for codigo, *_ in ZONAS]},
    )
