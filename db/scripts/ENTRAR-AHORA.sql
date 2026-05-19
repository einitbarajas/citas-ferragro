-- =============================================================================
-- EMERGENCIA: desbloquea login + deja ebarajas@ferragro.com con FerragroPortal2026!
-- Render → ferragro-db → Connect → pegar TODO y ejecutar.
-- =============================================================================

BEGIN;

-- 1) Quitar bloqueos por intentos fallidos (toda la BD)
DELETE FROM "IntentosLogin";

-- 2) Hash válido para: FerragroPortal2026!
-- (generado con bcrypt Python, compatible con el API)

DO $$
DECLARE
  v_cred_id INTEGER;
  v_rol_admin INTEGER;
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

  DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = v_cred_id;

  IF NOT EXISTS (SELECT 1 FROM "Usuarios" WHERE "IdDocumento" = '90000001') THEN
    INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
    VALUES ('90000001', 'Administrador Portal', v_cred_id, v_rol_admin);
  ELSE
    UPDATE "Usuarios"
    SET "IdCredencial" = v_cred_id, "IdRol" = v_rol_admin, "NombreCompleto" = 'Administrador Portal'
    WHERE "IdDocumento" = '90000001';
  END IF;
END $$;

COMMIT;

-- Debe mostrar ebarajas@ferragro.com | Admin | 90000001
SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento", u."NombreCompleto"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE lower(c."Correo") = lower('ebarajas@ferragro.com');
