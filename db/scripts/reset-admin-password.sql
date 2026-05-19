-- Restablece Admin: correo admin@ferragro.com, documento 90000001, clave FerragroAdmin2026!
-- Ejecutar en Render → ferragro-db → Connect → pegar TODO y ejecutar.
-- (No hace falta conocer la contraseña actual; se reemplaza el hash en la BD.)

-- Hash bcrypt de: FerragroAdmin2026!
-- Si regeneras la clave, genera otro hash con backend: get_password_hash('TuClave')

UPDATE "Credenciales" c
SET "HashContrasena" = '$2b$12$AgJ/YKsj5G/zHQWUMs0F5efyeeLNpVsseU6W.V8aI1KNwDIkVOYSG'
FROM "Usuarios" u
WHERE u."IdCredencial" = c."IdCredencial"
  AND u."IdDocumento" = '90000001';

UPDATE "Credenciales"
SET "HashContrasena" = '$2b$12$AgJ/YKsj5G/zHQWUMs0F5efyeeLNpVsseU6W.V8aI1KNwDIkVOYSG'
WHERE lower("Correo") = lower('admin@ferragro.com');

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
