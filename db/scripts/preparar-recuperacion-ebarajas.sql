-- Prepara recuperación para ebarajas@ferragro.com (Logística, doc. 1095798357).
-- Ejecutar en Render → ferragro-db → Connect.

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
    RAISE NOTICE 'Credencial huérfana eliminada: %', cid;
  END IF;
END $$;

UPDATE "Credenciales" c
SET "Correo" = 'ebarajas@ferragro.com'
FROM "Usuarios" u
WHERE u."IdCredencial" = c."IdCredencial"
  AND u."IdDocumento" = '1095798357';

DELETE FROM "EstadoResetContrasena" e
USING "Usuarios" u
WHERE e."IdCredencial" = u."IdCredencial"
  AND u."IdDocumento" = '1095798357';
