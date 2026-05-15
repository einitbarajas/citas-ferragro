-- Credenciales sin usuario ni proveedor (correo bloqueado tras borrar mal).
-- Ejecutar en producción solo si el API aún no está actualizado.
-- Reemplaza el correo antes de ejecutar.

-- 1) Ver huérfanas
SELECT c."IdCredencial", c."Correo"
FROM "Credenciales" c
LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
WHERE u."IdDocumento" IS NULL AND p."IdNit" IS NULL;

-- 2) Borrar dependencias y credencial (cambiar correo)
-- DELETE FROM "PerfilFoto" WHERE "IdCredencial" IN (
--   SELECT c."IdCredencial" FROM "Credenciales" c
--   LEFT JOIN "Usuarios" u ON u."IdCredencial" = c."IdCredencial"
--   LEFT JOIN "Proveedores" p ON p."IdCredencial" = c."IdCredencial"
--   WHERE u."IdDocumento" IS NULL AND p."IdNit" IS NULL AND c."Correo" = 'ebarajas@ferragro.com'
-- );
-- (repetir para SesionesRefresh, IntentosLogin, EstadoResetContrasena si aplica)
-- DELETE FROM "Credenciales" WHERE "Correo" = 'ebarajas@ferragro.com'
--   AND "IdCredencial" NOT IN (SELECT "IdCredencial" FROM "Usuarios")
--   AND "IdCredencial" NOT IN (SELECT "IdCredencial" FROM "Proveedores");
