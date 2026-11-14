"""Esquema inicial de review_db.

Revision ID: 0001
Revises:
Create Date: 2026-10-27

* Una reseña por turista y servicio (UNIQUE); un reporte por usuario y reseña (UNIQUE): las
  reglas se cumplen aunque lleguen dos envíos a la vez.
* JSONB solo para lo que no se consulta por columnas: aspectos (`{"LIMPIEZA": 5}`) y la
  respuesta del prestador (`{"texto": ..., "respondida_en": ...}`).
* Nada de reseñas ni reportes se borra: una reseña oculta es historia de la moderación.
  Solo se limpian el outbox publicado, `evento_procesado` viejo y la idempotencia vencida.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADOS = "'PUBLICADA','EN_REVISION','OCULTA'"
MOTIVOS = "'OFENSIVO','SPAM','FALSO','DATOS_PERSONALES','OTRO'"
ROLES_QUE_REPORTAN = "'Turista','Prestador'"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE resena (
            id                  uuid PRIMARY KEY,
            servicio_id         uuid NOT NULL,
            turista_id          uuid NOT NULL,
            puntuacion          smallint NOT NULL CHECK (puntuacion BETWEEN 1 AND 5),
            aspectos            jsonb NOT NULL DEFAULT '{{}}',
            comentario          text,
            respuesta           jsonb,
            ultima_visita       date NOT NULL,
            estado              text NOT NULL CHECK (estado IN ({ESTADOS})),
            reportes_pendientes integer NOT NULL DEFAULT 0 CHECK (reportes_pendientes >= 0),
            creada_en           timestamptz NOT NULL,
            editada_en          timestamptz,
            version             integer NOT NULL DEFAULT 1,
            CONSTRAINT uq_resena_turista_servicio UNIQUE (turista_id, servicio_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_resena_servicio ON resena (servicio_id, creada_en DESC)")
    op.execute("CREATE INDEX ix_resena_turista ON resena (turista_id, creada_en DESC)")
    # Cola de moderación: solo las que esperan al Administrador.
    op.execute(
        "CREATE INDEX ix_resena_moderacion ON resena (estado, reportes_pendientes DESC)"
        " WHERE reportes_pendientes > 0 OR estado = 'EN_REVISION'"
    )

    op.execute(
        f"""
        CREATE TABLE reporte_resena (
            id           uuid PRIMARY KEY,
            resena_id    uuid NOT NULL REFERENCES resena (id) ON DELETE CASCADE,
            usuario_id   uuid NOT NULL,
            rol          text NOT NULL CHECK (rol IN ({ROLES_QUE_REPORTAN})),
            motivo       text NOT NULL CHECK (motivo IN ({MOTIVOS})),
            detalle      text,
            es_dueno     boolean NOT NULL DEFAULT false,
            reportado_en timestamptz NOT NULL,
            resuelto_en  timestamptz,
            CONSTRAINT uq_reporte_resena_usuario UNIQUE (resena_id, usuario_id)
        )
        """
    )
    # Límite de reportes por hora de cada usuario.
    op.execute("CREATE INDEX ix_reporte_usuario ON reporte_resena (usuario_id, reportado_en)")
    op.execute(
        "CREATE INDEX ix_reporte_abiertos ON reporte_resena (resena_id) WHERE resuelto_en IS NULL"
    )

    # Proyección de reserva.finalizada: quién puede reseñar y el mes de su última visita.
    op.execute(
        """
        CREATE TABLE elegibilidad_resena (
            turista_id    uuid NOT NULL,
            servicio_id   uuid NOT NULL,
            ultima_visita date NOT NULL,
            PRIMARY KEY (turista_id, servicio_id)
        )
        """
    )

    # Proyección de servicio.publicado: dueño de cada servicio.
    op.execute(
        """
        CREATE TABLE servicio_dueno (
            servicio_id          uuid PRIMARY KEY,
            prestador_usuario_id uuid NOT NULL,
            version              integer NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_servicio_dueno_prestador ON servicio_dueno (prestador_usuario_id)")

    # Idempotencia de consumidores (ADR-008): evento ya aplicado por cada consumidor.
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
    op.execute("CREATE INDEX ix_evento_procesado_fecha ON evento_procesado (procesado_en)")

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

    # Idempotency-Key de formularios (Plan §6.8). Sin respuesta (estado_http NULL) está en
    # proceso; `expira_en` es 60 s en proceso y 48 h con la respuesta guardada.
    op.execute(
        """
        CREATE TABLE idempotencia (
            clave       text PRIMARY KEY,
            estado_http integer,
            cuerpo      bytea,
            cabeceras   jsonb,
            expira_en   timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_idempotencia_expira ON idempotencia (expira_en)")


def downgrade() -> None:
    for tabla in (
        "idempotencia",
        "outbox",
        "evento_procesado",
        "servicio_dueno",
        "elegibilidad_resena",
        "reporte_resena",
        "resena",
    ):
        op.execute(f"DROP TABLE {tabla}")
