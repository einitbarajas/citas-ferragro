-- Liberar ebarajas@ferragro.com si quedó credencial huérfana (sin usuario ni proveedor).
-- Ejecutar en Render → ferragro-db → Connect → Query (o psql con External URL).

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

  IF cid IS NULL THEN
    RAISE NOTICE 'No hay credencial huérfana para ese correo.';
    RETURN;
  END IF;

  DELETE FROM "PerfilFoto" WHERE "IdCredencial" = cid;
  DELETE FROM "SesionesRefresh" WHERE "IdCredencial" = cid;
  DELETE FROM "IntentosLogin" WHERE "IdCredencial" = cid;
  DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = cid;
  UPDATE "AuditoriaLogin" SET "IdCredencial" = NULL WHERE "IdCredencial" = cid;
  DELETE FROM "Credenciales" WHERE "IdCredencial" = cid;
  RAISE NOTICE 'Credencial % liberada.', cid;
END $$;
