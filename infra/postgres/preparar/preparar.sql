-- Lo que los servicios necesitan dentro de sus bases y no pueden crear ellos mismos. Lo ejecuta
-- el servicio postgres-preparar en cada arranque; repetirlo no cambia nada.

-- iam_db: la app se conecta con su propio rol, porque la migración inicial le revoca permisos
-- sobre la bitácora y eso no tiene efecto sobre un superusuario (C-03, C-55).
SELECT format('CREATE ROLE iam_user LOGIN PASSWORD %L', :'iam_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'iam_user')
\gexec

ALTER ROLE iam_user PASSWORD :'iam_password';
ALTER DATABASE iam_db OWNER TO iam_user;

-- recommendation_db: el servicio no tiene migraciones; su esquema es un script SQL.
\connect recommendation_db

SELECT to_regclass('public.recomendacion_log') IS NULL AS falta_tabla
\gset

\if :falta_tabla
\i /recommendation/01-recomendacion-log.sql
\endif
