-- Plantilla de roles PostgreSQL (mínimo privilegio). Ejecutar manualmente tras revisión DBA.
-- Reemplaza contraseñas y nombres de base de datos según tu entorno.

-- Ejemplo (comentado):
-- CREATE ROLE app_ferragro LOGIN PASSWORD '***';
-- GRANT CONNECT ON DATABASE db_trabajo TO app_ferragro;
-- GRANT USAGE ON SCHEMA public TO app_ferragro;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_ferragro;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_ferragro;

COMMENT ON SCHEMA public IS 'Ajustar GRANTs según usuario de aplicación vs usuario de migraciones.';
