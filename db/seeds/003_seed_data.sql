-- Seed de datos para ambiente local/desarrollo
-- Ejecutar despues de:
--   1) db/init/001_schema.sql
--   2) db/init/002_audit_triggers.sql

BEGIN;

-- Limpiar datos respetando dependencias
TRUNCATE TABLE
  "HistorialCambios",
  "Citas",
  "Proveedores",
  "Usuarios",
  "Credenciales",
  "Rol"
RESTART IDENTITY CASCADE;

-- Roles base
INSERT INTO "Rol" ("Nombre")
VALUES
  ('Admin'),
  ('Logistica'),
  ('Proveedor')
ON CONFLICT ("Nombre") DO NOTHING;

-- Credenciales de usuarios internos
INSERT INTO "Credenciales" ("Correo", "HashContrasena")
VALUES
  ('admin@ferragro.com', '$2b$12$EjemploHashAdmin'),
  ('logistica@ferragro.com', '$2b$12$EjemploHashLogistica'),
  ('proveedor1@acero.com', '$2b$12$EjemploHashProv1'),
  ('proveedor2@cemento.com', '$2b$12$EjemploHashProv2')
ON CONFLICT ("Correo") DO NOTHING;

-- Usuarios internos
INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
SELECT '12345678', 'Administrador General', c."IdCredencial", r."Id"
FROM "Credenciales" c
JOIN "Rol" r ON r."Nombre" = 'Admin'
WHERE c."Correo" = 'admin@ferragro.com'
ON CONFLICT ("IdDocumento") DO NOTHING;

INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
SELECT '23456789', 'Coordinador Logistica', c."IdCredencial", r."Id"
FROM "Credenciales" c
JOIN "Rol" r ON r."Nombre" = 'Logistica'
WHERE c."Correo" = 'logistica@ferragro.com'
ON CONFLICT ("IdDocumento") DO NOTHING;

-- Proveedores (CorreoEmpresa alineado con Credenciales para login unificado)
INSERT INTO "Proveedores" (
  "IdNit",
  "DigitoVerificacion",
  "NombreEmpresa",
  "CorreoEmpresa",
  "IdCredencial",
  "NombrePersonaResponsable",
  "DocumentoPersonaResponsable"
)
SELECT
  900123456,
  '7',
  'Aceros Andinos SAS',
  c."Correo",
  c."IdCredencial",
  'Juan Perez',
  '34567890'
FROM "Credenciales" c
WHERE c."Correo" = 'proveedor1@acero.com'
ON CONFLICT ("IdNit") DO NOTHING;

INSERT INTO "Proveedores" (
  "IdNit",
  "DigitoVerificacion",
  "NombreEmpresa",
  "CorreoEmpresa",
  "IdCredencial",
  "NombrePersonaResponsable",
  "DocumentoPersonaResponsable"
)
SELECT
  900654321,
  '3',
  'Cementos del Norte SAS',
  c."Correo",
  c."IdCredencial",
  'Maria Gomez',
  '45678901'
FROM "Credenciales" c
WHERE c."Correo" = 'proveedor2@cemento.com'
ON CONFLICT ("IdNit") DO NOTHING;

-- Definir actor para triggers de auditoria en Citas
SELECT set_config('app.current_actor', '12345678', true);

-- Citas de ejemplo
INSERT INTO "Citas" (
  "IdProveedor",
  "DescripcionMaterial",
  "FechaHoraInicio",
  "DuracionMinutos",
  "Estado"
)
VALUES
  (900123456, '2 toneladas de varilla corrugada', NOW() + INTERVAL '2 days', 90, 'sin_revision'),
  (900654321, '50 sacos de cemento gris', NOW() + INTERVAL '3 days', 120, 'revisado'),
  (900123456, 'Malla electrosoldada para obra', NOW() + INTERVAL '4 days', 90, 'cancelado');

COMMIT;
