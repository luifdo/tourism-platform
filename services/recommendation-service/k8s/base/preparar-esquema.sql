-- Crea la tabla recomendacion_log si falta. El servicio no tiene migraciones; el esquema es
-- 01-recomendacion-log.sql (copia de ../../db/, porque Kustomize no lee fuera de esta carpeta).
-- Con varias réplicas arrancando a la vez, el candado deja pasar a una sola y las demás ya la encuentran creada.
SELECT pg_advisory_xact_lock(8005);

SELECT to_regclass('public.recomendacion_log') IS NULL AS falta_tabla
\gset

\if :falta_tabla
\i /sql/01-recomendacion-log.sql
\endif
