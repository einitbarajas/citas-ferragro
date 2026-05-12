-- =============================================================================
-- Credenciales: INSERT con contraseña en texto plano (hash bcrypt en servidor)
-- Requiere extensión pgcrypto (incluida en PostgreSQL estándar / contrib).
-- Uso en pgAdmin:
--   SELECT credenciales_create_plain('correo@ejemplo.com', 'MiClaveSegura12');
-- El API Python (bcrypt) puede verificar estos hashes sin cambios.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION credenciales_create_plain(
  p_correo VARCHAR(255),
  p_contrasena_plano TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_id INTEGER;
  v_plain TEXT;
BEGIN
  v_plain := trim(p_contrasena_plano);
  IF v_plain IS NULL OR char_length(v_plain) < 6 THEN
    RAISE EXCEPTION 'credenciales_create_plain: la contraseña debe tener al menos 6 caracteres'
      USING ERRCODE = '23514';
  END IF;

  INSERT INTO "Credenciales" ("Correo", "HashContrasena")
  VALUES (p_correo, crypt(v_plain, gen_salt('bf', 12)))
  RETURNING "IdCredencial" INTO v_id;

  RETURN v_id;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'credenciales_create_plain: el correo "%" ya está registrado', p_correo
      USING ERRCODE = '23505';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'credenciales_create_plain: %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'credenciales_create_plain: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION credenciales_create_plain(VARCHAR, TEXT) IS 'Inserta credenciales hasheando la contraseña con bcrypt (pgcrypto).';
