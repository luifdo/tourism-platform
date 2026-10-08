-- Una base lógica por servicio dentro de la misma instancia de PostgreSQL (Database-per-Service).
-- Ver "Comparación de Alternativas Arquitectónicas", sección 4.4.
-- Se ejecuta solo la primera vez que se crea el volumen de datos.

CREATE DATABASE iam_db;
CREATE DATABASE catalog_db;
CREATE DATABASE booking_db;

\connect catalog_db
CREATE EXTENSION IF NOT EXISTS postgis;
