-- Restablece contraseña del Admin (documento 90000001) a FerragroAdmin2026!
-- Ejecutar en Render → ferragro-db → Connect → Query (o psql con External URL).

DO $$
DECLARE
  cid INTEGER;
BEGIN
  SELECT u."IdCredencial" INTO cid
  FROM "Usuarios" u
  WHERE u."IdDocumento" = '90000001'
  LIMIT 1;

  IF cid IS NULL THEN
    RAISE EXCEPTION 'No existe usuario Admin con documento 90000001.';
  END IF;

  PERFORM credenciales_update_password_plain(cid, 'FerragroAdmin2026!');

  DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = cid;

  RAISE NOTICE 'Admin listo: correo en Credenciales, documento 90000001, clave FerragroAdmin2026!';
END $$;
