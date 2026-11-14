"""Tipo de servicio, unidad de la tarifa, atributos por tipo y la categoría TRANSPORTE.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23

* `tipo` define la categoría y qué bloques de atributos usa el servicio (la regla vive en el
  dominio, `TipoServicio`); `categoria` se sigue guardando para los filtros e índices.
* `unidad_tarifa` acompaña a `tarifa_base`: sin ella no se comparan precios.
* `atributos` (JSONB) guarda los bloques del tipo; el índice GIN con `jsonb_path_ops` sirve a
  los filtros con `@>` (idiomas, accesible, mascotas, nivel físico, pagos...).
* Las listas se copian aquí y no se importan de `app`: una migración no cambia aunque el
  código siga evolucionando.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIAS_ANTES = "'PLAYA','NATURALEZA','CULTURA','GASTRONOMIA','AVENTURA','ALOJAMIENTO'"
CATEGORIAS = CATEGORIAS_ANTES + ",'TRANSPORTE'"
TIPOS = (
    "'HOTEL','HOSTAL','POSADA_ECOHOTEL','GLAMPING_CAMPING','APARTAMENTO_TURISTICO',"
    "'RESTAURANTE','CAFE_BAR','EXPERIENCIA_GASTRONOMICA','TOUR_GUIADO','SENDERISMO',"
    "'DEPORTE_ACUATICO','AVISTAMIENTO','RESERVA_PARQUE','ACCESO_PLAYA','ALQUILER_EQUIPO',"
    "'TOUR_CULTURAL','MUSEO_SITIO','EXPERIENCIA_COMUNITARIA','EVENTO_FESTIVAL',"
    "'TRANSPORTE_MARITIMO','TRASLADO_TERRESTRE'"
)
UNIDADES = "'POR_PERSONA','POR_NOCHE','POR_GRUPO','POR_UNIDAD','POR_HORA','POR_DIA'"

# Tipo para filas anteriores a esta migración (el prestador lo corrige al editar).
TIPO_POR_CATEGORIA = """
    CASE categoria
        WHEN 'PLAYA' THEN 'ACCESO_PLAYA'
        WHEN 'NATURALEZA' THEN 'RESERVA_PARQUE'
        WHEN 'CULTURA' THEN 'TOUR_CULTURAL'
        WHEN 'GASTRONOMIA' THEN 'RESTAURANTE'
        WHEN 'AVENTURA' THEN 'TOUR_GUIADO'
        WHEN 'ALOJAMIENTO' THEN 'HOSTAL'
    END
"""


def upgrade() -> None:
    op.execute("ALTER TABLE atractivo_servicio DROP CONSTRAINT atractivo_servicio_categoria_check")
    op.execute(
        f"ALTER TABLE atractivo_servicio ADD CONSTRAINT atractivo_servicio_categoria_check"
        f" CHECK (categoria IN ({CATEGORIAS}))"
    )
    op.execute(
        """
        ALTER TABLE atractivo_servicio
            ADD COLUMN tipo text,
            ADD COLUMN unidad_tarifa text,
            ADD COLUMN atributos jsonb NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        f"UPDATE atractivo_servicio SET tipo = {TIPO_POR_CATEGORIA}, unidad_tarifa = 'POR_PERSONA'"
    )
    op.execute(
        f"""
        ALTER TABLE atractivo_servicio
            ALTER COLUMN tipo SET NOT NULL,
            ALTER COLUMN unidad_tarifa SET NOT NULL,
            ADD CONSTRAINT atractivo_servicio_tipo_check CHECK (tipo IN ({TIPOS})),
            ADD CONSTRAINT atractivo_servicio_unidad_tarifa_check
                CHECK (unidad_tarifa IN ({UNIDADES})),
            ADD CONSTRAINT atractivo_servicio_atributos_check
                CHECK (jsonb_typeof(atributos) = 'object')
        """
    )
    op.execute("CREATE INDEX ix_servicio_tipo ON atractivo_servicio (tipo) WHERE activo")
    op.execute(
        "CREATE INDEX ix_servicio_atributos ON atractivo_servicio"
        " USING gin (atributos jsonb_path_ops) WHERE activo"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_servicio_atributos")
    op.execute("DROP INDEX ix_servicio_tipo")
    op.execute(
        "ALTER TABLE atractivo_servicio DROP COLUMN atributos, DROP COLUMN unidad_tarifa,"
        " DROP COLUMN tipo"
    )
    # Un servicio de TRANSPORTE no cabe en el esquema anterior: bajar falla si existe alguno.
    op.execute("ALTER TABLE atractivo_servicio DROP CONSTRAINT atractivo_servicio_categoria_check")
    op.execute(
        f"ALTER TABLE atractivo_servicio ADD CONSTRAINT atractivo_servicio_categoria_check"
        f" CHECK (categoria IN ({CATEGORIAS_ANTES}))"
    )
