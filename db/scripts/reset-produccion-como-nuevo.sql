-- =============================================================================
-- PRODUCCIÓN (Render → ferragro-db): borra TODO y deja solo 1 Admin.
--
-- Portal: https://frontend-ferragro.vercel.app
-- Admin:  ebarajas@ferragro.com  |  FerragroPortal2026!
--
-- Ejecutar TODO en Render → ferragro-db → Connect (PSQL).
-- Vercel no guarda usuarios; solo hace falta esta BD en Render.
-- =============================================================================

BEGIN;

DO $$
BEGIN
  IF to_regclass('public."Notificaciones"') IS NOT NULL THEN
    TRUNCATE TABLE "Notificaciones" RESTART IDENTITY CASCADE;
  END IF;
END $$;

TRUNCATE TABLE
  "HistorialCambios",
  "EjecucionesRecordatorio",
  "Citas",
  "Proveedores",
  "Usuarios",
  "PerfilFoto",
  "SesionesRefresh",
  "IntentosLogin",
  "AuditoriaLogin",
  "EstadoResetContrasena",
  "Credenciales",
  "FranjasPermitidasCitaFecha",
  "FranjasPermitidasCita",
  "AuditoriaSistema"
RESTART IDENTITY CASCADE;

INSERT INTO "Rol" ("Nombre")
VALUES ('Admin'), ('Logistica'), ('Proveedor')
ON CONFLICT ("Nombre") DO NOTHING;

INSERT INTO "FranjasPermitidasCita" ("HoraInicio", "HoraFin", "Orden")
VALUES
  ('08:00'::time, '11:00'::time, 1),
  ('13:00'::time, '16:00'::time, 2);

DO $$
DECLARE
  v_cred_id INTEGER;
  v_rol_admin INTEGER;
  v_email CONSTANT TEXT := 'ebarajas@ferragro.com';
  -- Contraseña en claro: FerragroPortal2026! (hash bcrypt Python, compatible con el API)
  v_hash CONSTANT TEXT := '$2b$12$aUcXWqjg4WLU0Jcc77RmRevmIG/NfKrJgn.j3HXm9A14LndZm8Xni';
BEGIN
  SELECT "Id" INTO v_rol_admin FROM "Rol" WHERE "Nombre" = 'Admin' LIMIT 1;
  IF v_rol_admin IS NULL THEN
    RAISE EXCEPTION 'No existe el rol Admin. Ejecuta db/run-database-all.ps1 contra esta BD primero.';
  END IF;

  INSERT INTO "Credenciales" ("Correo", "HashContrasena")
  VALUES (v_email, v_hash)
  RETURNING "IdCredencial" INTO v_cred_id;

  INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
  VALUES ('90000001', 'Administrador Portal', v_cred_id, v_rol_admin);
END $$;

COMMIT;

SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento", u."NombreCompleto"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol";
