-- Idempotente: en una base ya creada el tipo existe y CREATE TYPE fallaría.
DO $$
BEGIN
  CREATE TYPE "EstadoCita" AS ENUM ('sin_revision', 'revisado', 'finalizada', 'no_presentada', 'cancelado');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  ALTER TYPE "EstadoCita" ADD VALUE IF NOT EXISTS 'finalizada';
  ALTER TYPE "EstadoCita" ADD VALUE IF NOT EXISTS 'no_presentada';
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS "Rol" (
  "Id" SERIAL PRIMARY KEY,
  "Nombre" VARCHAR(40) UNIQUE NOT NULL
);

-- Credenciales compartidas: el mismo correo/clave sirve para login unificado.
-- Se enlaza desde "Usuarios" (Admin, Logistica) o desde "Proveedores" (Proveedor).
CREATE TABLE IF NOT EXISTS "Credenciales" (
  "IdCredencial" SERIAL PRIMARY KEY,
  "Correo" VARCHAR(255) UNIQUE NOT NULL,
  "HashContrasena" VARCHAR(255) NOT NULL
);

INSERT INTO "Rol" ("Nombre")
VALUES ('Admin'), ('Logistica'), ('Proveedor')
ON CONFLICT ("Nombre") DO NOTHING;

CREATE TABLE IF NOT EXISTS "Usuarios" (
  "IdDocumento" VARCHAR(30) PRIMARY KEY,
  "NombreCompleto" VARCHAR(120) NOT NULL,
  "IdCredencial" INTEGER UNIQUE NOT NULL REFERENCES "Credenciales"("IdCredencial"),
  "IdRol" INTEGER NOT NULL REFERENCES "Rol"("Id"),
  CONSTRAINT "ChkUsuariosIdDocumentoPorRol" CHECK (
    "IdDocumento" ~ '^[0-9]{7,10}$'
  )
);

CREATE TABLE IF NOT EXISTS "Proveedores" (
  "IdNit" NUMERIC(10,0) PRIMARY KEY,
  "DigitoVerificacion" VARCHAR(1) NOT NULL,
  "NombreEmpresa" VARCHAR(160) NOT NULL,
  "CorreoEmpresa" VARCHAR(255) UNIQUE NOT NULL,
  "IdCredencial" INTEGER UNIQUE NOT NULL REFERENCES "Credenciales"("IdCredencial"),
  "NombrePersonaResponsable" VARCHAR(160) NOT NULL,
  "DocumentoPersonaResponsable" VARCHAR(30) NOT NULL,
  CONSTRAINT "ChkProveedoresDocumentoPersonaResponsable" CHECK (
    "DocumentoPersonaResponsable" ~ '^[0-9]{7,10}$'
  ),
  CONSTRAINT "ChkProveedoresDigitoVerificacion" CHECK (
    "DigitoVerificacion" ~ '^[0-9]{1}$'
  )
);

-- Migracion: tablas creadas sin "CorreoEmpresa" (CREATE TABLE IF NOT EXISTS no altera columnas).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'Proveedores'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'CorreoEmpresa'
  ) THEN
    ALTER TABLE "Proveedores" ADD COLUMN "CorreoEmpresa" VARCHAR(255);
    UPDATE "Proveedores" p
    SET "CorreoEmpresa" = c."Correo"
    FROM "Credenciales" c
    WHERE p."IdCredencial" = c."IdCredencial";
    UPDATE "Proveedores"
    SET "CorreoEmpresa" = ('migracion-' || trim(both FROM "IdNit"::text) || '@local.invalid')
    WHERE "CorreoEmpresa" IS NULL;
    ALTER TABLE "Proveedores" ALTER COLUMN "CorreoEmpresa" SET NOT NULL;
    BEGIN
      ALTER TABLE "Proveedores" ADD CONSTRAINT "Proveedores_CorreoEmpresa_key" UNIQUE ("CorreoEmpresa");
    EXCEPTION
      WHEN duplicate_object THEN NULL;
      WHEN unique_violation THEN
        RAISE EXCEPTION 'migracion Proveedores.CorreoEmpresa: hay correos duplicados; corrija datos y vuelva a ejecutar'
          USING ERRCODE = '23505';
    END;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "Citas" (
  "Id" SERIAL PRIMARY KEY,
  "IdProveedor" NUMERIC(10,0) NOT NULL REFERENCES "Proveedores"("IdNit"),
  "DescripcionMaterial" TEXT NOT NULL,
  "FechaHoraInicio" TIMESTAMPTZ NOT NULL,
  "DuracionMinutos" INTEGER NOT NULL DEFAULT 90,
  "Estado" "EstadoCita" NOT NULL DEFAULT 'sin_revision'
);

-- IdActor: documento de "Usuarios" o "IdProveedor"::text (auditoría / triggers); sin FK para no bloquear proveedores.
CREATE TABLE IF NOT EXISTS "HistorialCambios" (
  "Id" SERIAL PRIMARY KEY,
  "IdActor" VARCHAR(30) NOT NULL,
  "IdCita" INTEGER NOT NULL REFERENCES "Citas"("Id"),
  "Accion" VARCHAR(80) NOT NULL,
  "Descripcion" TEXT NOT NULL,
  "CreadoEn" TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE "Credenciales" IS 'Login unificado por correo; enlazada a un Usuario interno o a un Proveedor.';
COMMENT ON COLUMN "HistorialCambios"."IdActor" IS 'Identificador del actor: IdDocumento (Usuarios) o IdProveedor en texto.';

CREATE INDEX IF NOT EXISTS "IdxCredencialesCorreo" ON "Credenciales"("Correo");
CREATE INDEX IF NOT EXISTS "IdxUsuariosIdRol" ON "Usuarios"("IdRol");
CREATE INDEX IF NOT EXISTS "IdxUsuariosIdCredencial" ON "Usuarios"("IdCredencial");
CREATE INDEX IF NOT EXISTS "IdxProveedoresNombreEmpresa" ON "Proveedores"("NombreEmpresa");
CREATE INDEX IF NOT EXISTS "IdxProveedoresCorreoEmpresa" ON "Proveedores"("CorreoEmpresa");
CREATE INDEX IF NOT EXISTS "IdxProveedoresIdCredencial" ON "Proveedores"("IdCredencial");
CREATE INDEX IF NOT EXISTS "IdxCitasFechaHoraInicio" ON "Citas"("FechaHoraInicio");
CREATE INDEX IF NOT EXISTS "IdxCitasIdProveedor" ON "Citas"("IdProveedor");
CREATE INDEX IF NOT EXISTS "IdxHistorialCambiosIdActor" ON "HistorialCambios"("IdActor");
