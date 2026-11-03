-- Esquema de recommendation_db (SRS, modelo de datos). PostgreSQL lo ejecuta una sola vez,
-- cuando se crea el volumen; la base la crea la imagen a partir de POSTGRES_DB.
-- No se guarda el texto de las conversaciones (Ley 1581): solo qué se recomendó y por qué.

CREATE TABLE recomendacion_log (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversacion_id     uuid        NOT NULL,
    turista_id          uuid        NOT NULL,
    -- Referencia lógica a catalog_db; no hay llave foránea entre bases.
    servicio_id         uuid        NOT NULL,
    justificacion       text        NOT NULL CHECK (btrim(justificacion) <> ''),
    herramientas_usadas jsonb       NOT NULL DEFAULT '[]'::jsonb,
    modelo              text        NOT NULL,
    fecha_generacion    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_recomendacion_log_conversacion_id ON recomendacion_log (conversacion_id);
CREATE INDEX ix_recomendacion_log_turista_id ON recomendacion_log (turista_id);
