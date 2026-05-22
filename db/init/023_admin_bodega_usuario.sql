-- Usuario administrador de bodega en producción (idempotente).
-- Contraseña: FerragroPortal2026! (mismo hash que admin portal en ENTRAR-AHORA.sql)

INSERT INTO "Rol" ("Nombre")
VALUES ('AdminBodega')
ON CONFLICT ("Nombre") DO NOTHING;

DO $$
DECLARE
  v_rol INTEGER;
  v_cred INTEGER;
  v_doc CONSTANT TEXT := '90000002';
  v_email CONSTANT TEXT := 'admin.bodega@ferragro.com';
  v_hash CONSTANT TEXT := '$2b$12$aUcXWqjg4WLU0Jcc77RmRevmIG/NfKrJgn.j3HXm9A14LndZm8Xni';
  v_nombre CONSTANT TEXT := 'Administrador de Bodega';
BEGIN
  SELECT "Id" INTO v_rol FROM "Rol" WHERE "Nombre" = 'AdminBodega' LIMIT 1;
  IF v_rol IS NULL THEN
    RAISE EXCEPTION 'Falta rol AdminBodega; ejecute 020_admin_bodega.sql antes';
  END IF;

  SELECT c."IdCredencial" INTO v_cred
  FROM "Credenciales" c
  WHERE lower(c."Correo") = lower(v_email)
  LIMIT 1;

  IF v_cred IS NULL THEN
    INSERT INTO "Credenciales" ("Correo", "HashContrasena")
    VALUES (v_email, v_hash)
    RETURNING "IdCredencial" INTO v_cred;
  ELSE
    UPDATE "Credenciales"
    SET "HashContrasena" = v_hash, "Correo" = v_email
    WHERE "IdCredencial" = v_cred;
  END IF;

  DELETE FROM "Usuarios"
  WHERE "IdCredencial" = v_cred AND "IdDocumento" <> v_doc;

  IF NOT EXISTS (SELECT 1 FROM "Usuarios" WHERE "IdDocumento" = v_doc) THEN
    INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
    VALUES (v_doc, v_nombre, v_cred, v_rol);
  ELSE
    UPDATE "Usuarios"
    SET "IdCredencial" = v_cred,
        "IdRol" = v_rol,
        "NombreCompleto" = v_nombre
    WHERE "IdDocumento" = v_doc;
  END IF;

  -- Asignar todas las bodegas activas
  INSERT INTO "UsuariosBodegas" ("IdDocumento", "IdBodega")
  SELECT v_doc, b."Id"
  FROM "Bodegas" b
  WHERE b."Activa" = TRUE
  ON CONFLICT ("IdDocumento", "IdBodega") DO NOTHING;
END $$;
