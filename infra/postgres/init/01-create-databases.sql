-- The main POSTGRES_DB is created automatically by the postgres image.
-- This adds the separate database used by the HAPI FHIR server.
--
-- NOTE: this name must match POSTGRES_FHIR_DB in .env. If you change that
-- variable, update this file (docker-entrypoint-initdb.d scripts run before
-- environment-templated values are available here).
SELECT 'CREATE DATABASE medita_fhir'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medita_fhir')
\gexec
