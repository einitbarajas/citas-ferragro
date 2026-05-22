-- =============================================================================
-- ARREGLAR TODO EN PRODUCCIÓN (Render → ferragro-db → PSQL / Query)
-- 1) Columna Citas.IdBodega y tablas relacionadas (resumen idempotente)
-- 2) Rol AdminBodega
-- 3) Usuario administrador de bodega
--
-- Si falla por dependencias, ejecuta antes desde tu PC:
--   cd db
--   .\arreglar-esquema-produccion.ps1
-- =============================================================================

BEGIN;

-- --- Rol AdminBodega ---
INSERT INTO "Rol" ("Nombre")
VALUES ('Admin'), ('Logistica'), ('Proveedor'), ('AdminBodega')
ON CONFLICT ("Nombre") DO NOTHING;

-- --- Bodegas mínimas ---
CREATE TABLE IF NOT EXISTS "Bodegas" (
  "Id" SERIAL PRIMARY KEY,
  "Nombre" VARCHAR(120) NOT NULL,
  "Direccion" VARCHAR(255),
  "Activa" BOOLEAN NOT NULL DEFAULT TRUE,
  "Orden" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "UqBodegasNombre" UNIQUE ("Nombre")
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Bodegas' AND column_name = 'EquiposDescarga'
  ) THEN
    UPDATE "Bodegas" SET "EquiposDescarga" = 1 WHERE "EquiposDescarga" IS NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM "Bodegas" LIMIT 1) THEN
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'Bodegas' AND column_name = 'EquiposDescarga'
    ) THEN
      INSERT INTO "Bodegas" ("Nombre", "Direccion", "Activa", "Orden", "EquiposDescarga")
      VALUES ('Bodega principal', NULL, TRUE, 0, 1);
    ELSE
      INSERT INTO "Bodegas" ("Nombre", "Direccion", "Activa", "Orden")
      VALUES ('Bodega principal', NULL, TRUE, 0);
    END IF;
  END IF;
END $$;

-- --- Citas.IdBodega (corrige el error del log) ---
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Citas' AND column_name = 'IdBodega'
  ) THEN
    ALTER TABLE "Citas" ADD COLUMN "IdBodega" INTEGER REFERENCES "Bodegas"("Id");
    UPDATE "Citas" SET "IdBodega" = (SELECT MIN("Id") FROM "Bodegas") WHERE "IdBodega" IS NULL;
    ALTER TABLE "Citas" ALTER COLUMN "IdBodega" SET NOT NULL;
    CREATE INDEX IF NOT EXISTS "IdxCitasIdBodega" ON "Citas"("IdBodega");
  END IF;
END $$;

-- --- UsuariosBodegas ---
CREATE TABLE IF NOT EXISTS "UsuariosBodegas" (
  "IdDocumento" VARCHAR(30) NOT NULL REFERENCES "Usuarios"("IdDocumento") ON DELETE CASCADE,
  "IdBodega" INTEGER NOT NULL REFERENCES "Bodegas"("Id") ON DELETE CASCADE,
  PRIMARY KEY ("IdDocumento", "IdBodega")
);

-- --- Usuario Admin de bodega ---
DO $$
DECLARE
  v_rol INTEGER;
  v_cred INTEGER;
  v_doc CONSTANT TEXT := '90000002';
  v_email CONSTANT TEXT := 'admin.bodega@ferragro.com';
  v_hash CONSTANT TEXT := '$2b$12$aUcXWqjg4WLU0Jcc77RmRevmIG/NfKrJgn.j3HXm9A14LndZm8Xni';
  v_nombre CONSTANT TEXT := 'Administrador de Bodega';
BEGIN
  SELECT "Id" INTO v_rol FROM "Rol" WHERE "Nombre" = 'AdminBodega' LIMIT 1;

  SELECT c."IdCredencial" INTO v_cred
  FROM "Credenciales" c WHERE lower(c."Correo") = lower(v_email) LIMIT 1;

  IF v_cred IS NULL THEN
    INSERT INTO "Credenciales" ("Correo", "HashContrasena")
    VALUES (v_email, v_hash) RETURNING "IdCredencial" INTO v_cred;
  ELSE
    UPDATE "Credenciales" SET "HashContrasena" = v_hash WHERE "IdCredencial" = v_cred;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM "Usuarios" WHERE "IdDocumento" = v_doc) THEN
    INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
    VALUES (v_doc, v_nombre, v_cred, v_rol);
  ELSE
    UPDATE "Usuarios"
    SET "IdCredencial" = v_cred, "IdRol" = v_rol, "NombreCompleto" = v_nombre
    WHERE "IdDocumento" = v_doc;
  END IF;

  INSERT INTO "UsuariosBodegas" ("IdDocumento", "IdBodega")
  SELECT v_doc, b."Id" FROM "Bodegas" b WHERE b."Activa" = TRUE
  ON CONFLICT DO NOTHING;
END $$;

COMMIT;

SELECT 'OK' AS resultado, c."Correo", r."Nombre" AS rol, u."NombreCompleto"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE u."IdDocumento" IN ('90000001', '90000002')
ORDER BY u."IdDocumento";
