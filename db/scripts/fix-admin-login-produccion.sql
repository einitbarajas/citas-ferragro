-- Arregla login Admin en producción (Render → ferragro-db → Connect).
-- Preferir: db/scripts/cambiar-admin-a-ebarajas.sql (correo ebarajas@ferragro.com).
-- Este archivo: admin@ferragro.com | Contraseña: FerragroAdmin2026!
-- Ejecutar TODO de una vez.

DO $$
DECLARE
  v_id INTEGER;
  v_hash CONSTANT TEXT := '$2b$12$AgJ/YKsj5G/zHQWUMs0F5efyeeLNpVsseU6W.V8aI1KNwDIkVOYSG';
BEGIN
  SELECT c."IdCredencial" INTO v_id
  FROM "Credenciales" c
  WHERE lower(c."Correo") = lower('admin@ferragro.com')
  LIMIT 1;

  IF v_id IS NULL THEN
    RAISE EXCEPTION 'No existe admin@ferragro.com. Ejecuta antes db/scripts/reset-produccion-como-nuevo.sql';
  END IF;

  BEGIN
    PERFORM credenciales_update_password_plain(v_id, 'FerragroAdmin2026!');
  EXCEPTION
    WHEN undefined_function THEN
      UPDATE "Credenciales"
      SET "HashContrasena" = v_hash
      WHERE "IdCredencial" = v_id;
  END;
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

SELECT c."Correo", left(c."HashContrasena", 7) AS hash_prefijo, u."IdDocumento"
FROM "Credenciales" c
JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
WHERE lower(c."Correo") = lower('admin@ferragro.com');
