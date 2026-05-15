-- Liberar correo huérfano (sin usuario ni proveedor). Cambia el correo si hace falta.
-- Render → ferragro-db → Connect → ejecutar cada bloque en orden.

DELETE FROM "PerfilFoto"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial"
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
);

DELETE FROM "SesionesRefresh"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial"
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
);

DELETE FROM "IntentosLogin"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial"
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
);

DELETE FROM "EstadoResetContrasena"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial"
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
);

UPDATE "AuditoriaLogin"
SET "IdCredencial" = NULL
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial"
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
);

DELETE FROM "Credenciales"
WHERE "IdCredencial" IN (
  SELECT c."IdCredencial"
  FROM "Credenciales" c
  LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
  LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
  WHERE lower(c."Correo") = lower('ebarajas@ferragro.com')
    AND u."IdDocumento" IS NULL
    AND p."IdNit" IS NULL
);
