-- Datos mínimos idempotentes para pytest (CI / local). No hace TRUNCATE.
BEGIN;

INSERT INTO "Rol" ("Nombre")
VALUES ('Admin'), ('Logistica'), ('Proveedor'), ('AdminBodega')
ON CONFLICT ("Nombre") DO NOTHING;

INSERT INTO "Bodegas" ("Nombre", "Direccion", "Activa", "EquiposDescarga")
SELECT 'Bodega CI pytest', 'Solo pruebas automatizadas', TRUE, 2
WHERE NOT EXISTS (SELECT 1 FROM "Bodegas" WHERE "Activa" = TRUE);

UPDATE "Bodegas"
SET "EquiposDescarga" = GREATEST(COALESCE("EquiposDescarga", 1), 2)
WHERE "Id" = (SELECT MIN("Id") FROM "Bodegas" WHERE "Activa" = TRUE);

INSERT INTO "EquiposDescargaBodega" ("IdBodega", "Nombre", "Activo", "Orden")
SELECT b."Id", 'Equipo ' || gs.n::TEXT, TRUE, gs.n - 1
FROM "Bodegas" b
CROSS JOIN LATERAL generate_series(1, GREATEST(COALESCE(b."EquiposDescarga", 1), 2)) AS gs(n)
WHERE b."Activa" = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM "EquiposDescargaBodega" e WHERE e."IdBodega" = b."Id"
  );

UPDATE "Credenciales"
SET "Correo" = 'pytest-proveedor-ci@example.com'
WHERE "Correo" = 'pytest-proveedor@ferragro.test';

UPDATE "Proveedores"
SET "CorreoEmpresa" = 'pytest-proveedor-ci@example.com'
WHERE "CorreoEmpresa" = 'pytest-proveedor@ferragro.test';

INSERT INTO "Credenciales" ("Correo", "HashContrasena")
SELECT 'pytest-proveedor-ci@example.com', '$2b$12$EjemploHashSoloPruebasCI'
WHERE NOT EXISTS (
  SELECT 1 FROM "Credenciales" WHERE "Correo" = 'pytest-proveedor-ci@example.com'
);

INSERT INTO "Proveedores" (
  "IdNit",
  "DigitoVerificacion",
  "NombreEmpresa",
  "CorreoEmpresa",
  "IdCredencial",
  "NombrePersonaResponsable",
  "DocumentoPersonaResponsable",
  "EquiposDescarga"
)
SELECT
  8000000001,
  '1',
  'Proveedor CI pytest',
  c."Correo",
  c."IdCredencial",
  'Contacto pytest',
  '8000000001',
  1
FROM "Credenciales" c
WHERE c."Correo" = 'pytest-proveedor-ci@example.com'
  AND NOT EXISTS (SELECT 1 FROM "Proveedores" WHERE "IdNit" = 8000000001);

COMMIT;
