-- Admin: admin@ferragro.com | documento 90000001
-- Contraseña: FerragroAdmin2026!
-- También quita bloqueo por intentos fallidos (15 min).
-- Render → ferragro-db → Connect → ejecutar TODO.

DO $$
DECLARE
  v_id INTEGER;
  v_hash CONSTANT TEXT := '$2b$12$AgJ/YKsj5G/zHQWUMs0F5efyeeLNpVsseU6W.V8aI1KNwDIkVOYSG';
BEGIN
  SELECT c."IdCredencial" INTO v_id
  FROM "Credenciales" c
  WHERE lower(c."Correo") = lower('admin@ferragro.com')
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    BEGIN
      PERFORM credenciales_update_password_plain(v_id, 'FerragroAdmin2026!');
    EXCEPTION
      WHEN undefined_function THEN
        UPDATE "Credenciales" SET "HashContrasena" = v_hash WHERE "IdCredencial" = v_id;
    END;
  ELSE
    UPDATE "Credenciales" c
    SET "HashContrasena" = v_hash
    FROM "Usuarios" u
    WHERE u."IdCredencial" = c."IdCredencial"
      AND u."IdDocumento" = '90000001';

    UPDATE "Credenciales"
    SET "HashContrasena" = v_hash
    WHERE lower("Correo") = lower('admin@ferragro.com');
  END IF;
END $$;

DELETE FROM "EstadoResetContrasena"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial" FROM "Credenciales" c
  WHERE lower(c."Correo") = lower('admin@ferragro.com')
);

DELETE FROM "IntentosLogin"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial" FROM "Credenciales" c
  WHERE lower(c."Correo") = lower('admin@ferragro.com')
);
