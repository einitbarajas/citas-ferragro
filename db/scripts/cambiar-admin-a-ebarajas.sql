-- Admin (documento 90000001): correo → ebarajas@ferragro.com
-- Contraseña nueva: FerragroEbarajas2026!
-- Render → ferragro-db → Connect → ejecutar TODO.

-- Libera ebarajas@ferragro.com si quedó credencial huérfana (sin usuario ni proveedor)
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
    RAISE NOTICE 'Credencial huérfana ebarajas@ferragro.com eliminada (IdCredencial %).', cid;
  END IF;
END $$;

DO $$
DECLARE
  v_admin_cred INTEGER;
  v_conflict INTEGER;
  v_hash CONSTANT TEXT := '$2b$12$8N9DsCtno2fxWXt8h5TaWOy5kMvBHEKEeBsyK.JvEy2u9SDW/rzgi';
  v_new_email CONSTANT TEXT := 'ebarajas@ferragro.com';
  v_new_password CONSTANT TEXT := 'FerragroEbarajas2026!';
BEGIN
  SELECT u."IdCredencial" INTO v_admin_cred
  FROM "Usuarios" u
  JOIN "Rol" r ON r."Id" = u."IdRol"
  WHERE u."IdDocumento" = '90000001'
    AND r."Nombre" = 'Admin'
  LIMIT 1;

  IF v_admin_cred IS NULL THEN
    SELECT c."IdCredencial" INTO v_admin_cred
    FROM "Credenciales" c
    WHERE lower(c."Correo") IN (lower('admin@ferragro.com'), lower('ebarajas@ferragro.com'))
    ORDER BY CASE WHEN lower(c."Correo") = lower('ebarajas@ferragro.com') THEN 0 ELSE 1 END
    LIMIT 1;
  END IF;

  IF v_admin_cred IS NULL THEN
    RAISE EXCEPTION 'No se encontró usuario Admin (documento 90000001).';
  END IF;

  SELECT c."IdCredencial" INTO v_conflict
  FROM "Credenciales" c
  WHERE lower(c."Correo") = lower(v_new_email)
    AND c."IdCredencial" <> v_admin_cred
  LIMIT 1;

  IF v_conflict IS NOT NULL THEN
    RAISE EXCEPTION 'ebarajas@ferragro.com ya está en uso por otra cuenta (IdCredencial %). Libera o elimina esa cuenta antes.', v_conflict;
  END IF;

  UPDATE "Credenciales"
  SET "Correo" = v_new_email
  WHERE "IdCredencial" = v_admin_cred;

  BEGIN
    PERFORM credenciales_update_password_plain(v_admin_cred, v_new_password);
  EXCEPTION
    WHEN undefined_function THEN
      UPDATE "Credenciales"
      SET "HashContrasena" = v_hash
      WHERE "IdCredencial" = v_admin_cred;
  END;
END $$;

DELETE FROM "EstadoResetContrasena"
WHERE "IdCredencial" IN (
  SELECT u."IdCredencial" FROM "Usuarios" u WHERE u."IdDocumento" = '90000001'
);

DELETE FROM "IntentosLogin"
WHERE "IdCredencial" IN (
  SELECT u."IdCredencial" FROM "Usuarios" u WHERE u."IdDocumento" = '90000001'
);

SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento", u."NombreCompleto"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE u."IdDocumento" = '90000001';
