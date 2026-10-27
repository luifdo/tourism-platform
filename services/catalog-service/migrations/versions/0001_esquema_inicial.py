"""Esquema inicial de catalog_db.

Revision ID: 0001
Revises:
Create Date: 2026-10-18

* Puntos en `geography(Point, 4326)`: ST_DWithin y ST_Distance miden en metros. Se guardan
  `lat`/`lon` y `ubicacion` es una columna generada, para que nunca se desincronicen.
* Zonas en `geometry(MultiPolygon, 4326)`: un Polygon se guarda con ST_Multi.
* Textos de usuario bilingües en JSONB `{"es": ..., "en": ...}`; la búsqueda de texto usa
  una columna `tsvector` generada por idioma, sin tildes (unaccent) e indexada con GIN.
* Nada se borra físicamente: servicios, zonas, perfiles y alertas se desactivan.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIAS = "'PLAYA','NATURALEZA','CULTURA','GASTRONOMIA','AVENTURA','ALOJAMIENTO'"
ESTADOS = "'SOLICITADA','CONFIRMADA','RECHAZADA','CANCELADA','FINALIZADA'"
NIVELES_ALERTA = "'INFORMATIVA','PREVENTIVA','CRITICA'"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # unaccent() no es IMMUTABLE y no puede usarse en columnas generadas ni en índices;
    # esta envoltura fija el diccionario y sí lo es.
    op.execute(
        """
        CREATE FUNCTION f_unaccent(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
        """
    )

    op.execute(
        """
        CREATE TABLE prestador_perfil (
            id                   uuid PRIMARY KEY,
            usuario_id           uuid NOT NULL UNIQUE,
            razon_social         text,
            telefono             text,
            direccion            text,
            politica_cancelacion jsonb,
            activo               boolean NOT NULL DEFAULT true,
            version              integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            creado_en            timestamptz NOT NULL DEFAULT now(),
            actualizado_en       timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE zona (
            id       uuid PRIMARY KEY,
            codigo   text NOT NULL UNIQUE CHECK (codigo ~ '^[a-z0-9-]{2,40}$'),
            nombre   jsonb NOT NULL CHECK (nombre ? 'es'),
            poligono geometry(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(poligono)),
            activa   boolean NOT NULL DEFAULT true,
            version  integer NOT NULL DEFAULT 1 CHECK (version >= 1)
        )
        """
    )
    op.execute("CREATE INDEX ix_zona_poligono ON zona USING gist (poligono)")

    op.execute(
        f"""
        CREATE TABLE atractivo_servicio (
            id                         uuid PRIMARY KEY,
            prestador_id               uuid NOT NULL REFERENCES prestador_perfil (id),
            prestador_usuario_id       uuid NOT NULL,
            nombre                     jsonb NOT NULL CHECK (nombre ? 'es'),
            descripcion                jsonb NOT NULL CHECK (descripcion ? 'es'),
            categoria                  text NOT NULL CHECK (categoria IN ({CATEGORIAS})),
            lat                        double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
            lon                        double precision NOT NULL CHECK (lon BETWEEN -180 AND 180),
            ubicacion                  geography(Point, 4326) NOT NULL
                GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) STORED,
            tarifa_base                numeric(12, 2) NOT NULL CHECK (tarifa_base >= 0),
            capacidad_aforo_diario     integer NOT NULL CHECK (capacidad_aforo_diario >= 1),
            imagenes_urls              text[] NOT NULL DEFAULT '{{}}'
                CHECK (cardinality(imagenes_urls) <= 10),
            zona_id                    uuid REFERENCES zona (id),
            activo                     boolean NOT NULL DEFAULT true,
            desactivado_por_suspension boolean NOT NULL DEFAULT false,
            version                    integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            creado_en                  timestamptz NOT NULL,
            actualizado_en             timestamptz NOT NULL,
            busqueda_es tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('spanish', f_unaccent(coalesce(nombre ->> 'es', ''))), 'A')
                || setweight(to_tsvector('spanish', f_unaccent(coalesce(descripcion ->> 'es', ''))), 'B')
            ) STORED,
            busqueda_en tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', f_unaccent(coalesce(nombre ->> 'en', nombre ->> 'es', ''))), 'A')
                || setweight(to_tsvector('english', f_unaccent(coalesce(descripcion ->> 'en', descripcion ->> 'es', ''))), 'B')
            ) STORED
        )
        """
    )
    op.execute("CREATE INDEX ix_servicio_ubicacion ON atractivo_servicio USING gist (ubicacion)")
    op.execute("CREATE INDEX ix_servicio_busqueda_es ON atractivo_servicio USING gin (busqueda_es)")
    op.execute("CREATE INDEX ix_servicio_busqueda_en ON atractivo_servicio USING gin (busqueda_en)")
    op.execute(
        "CREATE INDEX ix_servicio_activo_categoria ON atractivo_servicio (categoria, tarifa_base)"
        " WHERE activo"
    )
    op.execute("CREATE INDEX ix_servicio_zona ON atractivo_servicio (zona_id)")
    op.execute("CREATE INDEX ix_servicio_prestador ON atractivo_servicio (prestador_id)")

    op.execute(
        f"""
        CREATE TABLE alerta_oficial (
            id                 uuid PRIMARY KEY,
            nivel              text NOT NULL CHECK (nivel IN ({NIVELES_ALERTA})),
            mensaje            jsonb NOT NULL CHECK (mensaje ? 'es'),
            entidad_usuario_id uuid NOT NULL,
            servicio_id        uuid REFERENCES atractivo_servicio (id),
            zona_id            uuid REFERENCES zona (id),
            fecha_expiracion   timestamptz NOT NULL,
            creada_en          timestamptz NOT NULL,
            activa             boolean NOT NULL DEFAULT true,
            CONSTRAINT ck_alerta_un_destino CHECK ((servicio_id IS NULL) <> (zona_id IS NULL))
        )
        """
    )
    op.execute("CREATE INDEX ix_alerta_vigente ON alerta_oficial (fecha_expiracion) WHERE activa")
    op.execute("CREATE INDEX ix_alerta_zona ON alerta_oficial (zona_id) WHERE activa")
    op.execute("CREATE INDEX ix_alerta_servicio ON alerta_oficial (servicio_id) WHERE activa")

    # Proyecciones alimentadas por eventos: sin llaves foráneas, para que un dato fuera de
    # orden nunca bloquee al consumidor (Database-per-Service, referencias lógicas).
    op.execute(
        f"""
        CREATE TABLE reserva_proyeccion (
            reserva_id       uuid PRIMARY KEY,
            servicio_id      uuid NOT NULL,
            prestador_id     uuid NOT NULL,
            turista_id       uuid NOT NULL,
            fecha_reserva    date NOT NULL,
            numero_personas  integer NOT NULL CHECK (numero_personas >= 1),
            estado           text NOT NULL CHECK (estado IN ({ESTADOS})),
            ultimo_evento_en timestamptz NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_reserva_fecha_servicio ON reserva_proyeccion"
        " (fecha_reserva, servicio_id) INCLUDE (estado, numero_personas)"
    )
    op.execute(
        "CREATE INDEX ix_reserva_prestador ON reserva_proyeccion (prestador_id, fecha_reserva)"
    )

    op.execute(
        """
        CREATE TABLE calificacion_resena (
            resena_id      uuid PRIMARY KEY,
            servicio_id    uuid NOT NULL,
            puntuacion     smallint NOT NULL CHECK (puntuacion BETWEEN 1 AND 5),
            actualizado_en timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_calificacion_servicio ON calificacion_resena (servicio_id)")

    # Idempotencia de consumidores: se inserta en la misma transacción que el efecto.
    op.execute(
        """
        CREATE TABLE evento_procesado (
            event_id     uuid NOT NULL,
            consumidor   text NOT NULL,
            procesado_en timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (event_id, consumidor)
        )
        """
    )

    # Outbox (ADR-008): el evento se guarda con el cambio y un relay lo publica después.
    op.execute(
        """
        CREATE TABLE outbox (
            event_id     uuid PRIMARY KEY,
            event_type   text NOT NULL,
            sobre        jsonb NOT NULL,
            creado_en    timestamptz NOT NULL DEFAULT now(),
            publicado_en timestamptz,
            intentos     integer NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX ix_outbox_pendientes ON outbox (creado_en) WHERE publicado_en IS NULL")


def downgrade() -> None:
    for tabla in (
        "outbox",
        "evento_procesado",
        "calificacion_resena",
        "reserva_proyeccion",
        "alerta_oficial",
        "atractivo_servicio",
        "zona",
        "prestador_perfil",
    ):
        op.execute(f"DROP TABLE {tabla}")
    op.execute("DROP FUNCTION f_unaccent(text)")
    # Las extensiones postgis y unaccent se conservan: pueden haberse creado fuera de esta
    # migración (infra/postgres/init) y borrarlas exige privilegios de superusuario.
