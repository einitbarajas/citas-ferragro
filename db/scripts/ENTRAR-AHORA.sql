-- =============================================================================
-- EMERGENCIA: desbloquea login + Admin ebarajas@ferragro.com / FerragroPortal2026!
-- (Si el correo estaba en Logística u otro usuario, lo reasigna solo al Admin.)
-- Render → ferragro-db → Connect → pegar TODO y ejecutar.
-- =============================================================================

BEGIN;

DELETE FROM "IntentosLogin";

DO $$
DECLARE
  v_cred_id INTEGER;
  v_rol_admin INTEGER;
  v_old_admin_cred INTEGER;
  v_email CONSTANT TEXT := 'ebarajas@ferragro.com';
  v_hash CONSTANT TEXT := '$2b$12$aUcXWqjg4WLU0Jcc77RmRevmIG/NfKrJgn.j3HXm9A14LndZm8Xni';
BEGIN
  INSERT INTO "Rol" ("Nombre")
  VALUES ('Admin'), ('Logistica'), ('Proveedor')
  ON CONFLICT ("Nombre") DO NOTHING;

  SELECT "Id" INTO v_rol_admin FROM "Rol" WHERE "Nombre" = 'Admin' LIMIT 1;

  SELECT c."IdCredencial" INTO v_cred_id
  FROM "Credenciales" c
  WHERE lower(c."Correo") = lower(v_email)
  LIMIT 1;

  IF v_cred_id IS NULL THEN
    INSERT INTO "Credenciales" ("Correo", "HashContrasena")
    VALUES (v_email, v_hash)
    RETURNING "IdCredencial" INTO v_cred_id;
  ELSE
    UPDATE "Credenciales"
    SET "HashContrasena" = v_hash, "Correo" = v_email
    WHERE "IdCredencial" = v_cred_id;
  END IF;

  -- El correo no puede estar en Logística y Admin a la vez (misma IdCredencial)
  DELETE FROM "Usuarios"
  WHERE "IdCredencial" = v_cred_id
    AND "IdDocumento" <> '90000001';

  SELECT u."IdCredencial" INTO v_old_admin_cred
  FROM "Usuarios" u
  WHERE u."IdDocumento" = '90000001'
  LIMIT 1;

  IF v_old_admin_cred IS NOT NULL AND v_old_admin_cred <> v_cred_id THEN
    DELETE FROM "PerfilFoto" WHERE "IdCredencial" = v_old_admin_cred;
    DELETE FROM "SesionesRefresh" WHERE "IdCredencial" = v_old_admin_cred;
    DELETE FROM "IntentosLogin" WHERE "IdCredencial" = v_old_admin_cred;
    DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = v_old_admin_cred;
    UPDATE "AuditoriaLogin" SET "IdCredencial" = NULL WHERE "IdCredencial" = v_old_admin_cred;
    DELETE FROM "Credenciales" c
    WHERE c."IdCredencial" = v_old_admin_cred
      AND NOT EXISTS (SELECT 1 FROM "Usuarios" u WHERE u."IdCredencial" = c."IdCredencial")
      AND NOT EXISTS (SELECT 1 FROM "Proveedores" p WHERE p."IdCredencial" = c."IdCredencial");
  END IF;

  IF NOT EXISTS (SELECT 1 FROM "Usuarios" WHERE "IdDocumento" = '90000001') THEN
    INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
    VALUES ('90000001', 'Administrador Portal', v_cred_id, v_rol_admin);
  ELSE
    UPDATE "Usuarios"
    SET "IdCredencial" = v_cred_id,
        "IdRol" = v_rol_admin,
        "NombreCompleto" = 'Administrador Portal'
    WHERE "IdDocumento" = '90000001';
  END IF;

  DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = v_cred_id;
END $$;

COMMIT;

SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento", u."NombreCompleto"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE lower(c."Correo") = lower('ebarajas@ferragro.com');
