-- Prepara ebarajas@ferragro.com para login y "Olvidé mi contraseña".
-- Render → ferragro-db → Connect → ejecutar TODO.

DO $$
DECLARE
  cid INTEGER;
BEGIN
  SELECT c."IdCredencial" INTO cid
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
  LIMIT 1;

  IF cid IS NOT NULL THEN
    DELETE FROM "PerfilFoto" WHERE "IdCredencial" = cid;
    DELETE FROM "SesionesRefresh" WHERE "IdCredencial" = cid;
    DELETE FROM "IntentosLogin" WHERE "IdCredencial" = cid;
    DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = cid;
    UPDATE "AuditoriaLogin" SET "IdCredencial" = NULL WHERE "IdCredencial" = cid;
    DELETE FROM "Credenciales" WHERE "IdCredencial" = cid;
  END IF;
END $$;

UPDATE "Credenciales" c
SET "Correo" = 'ebarajas@ferragro.com'
FROM "Usuarios" u
WHERE u."IdCredencial" = c."IdCredencial"
  AND u."IdDocumento" = '90000001';

DELETE FROM "IntentosLogin" il
USING "Credenciales" c
WHERE il."IdCredencial" = c."IdCredencial"
  AND lower(c."Correo") = lower('ebarajas@ferragro.com');

DELETE FROM "EstadoResetContrasena" e
USING "Credenciales" c
WHERE e."IdCredencial" = c."IdCredencial"
  AND lower(c."Correo") = lower('ebarajas@ferragro.com');

SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE lower(c."Correo") = lower('ebarajas@ferragro.com');
