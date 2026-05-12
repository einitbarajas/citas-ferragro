-- =============================================================================
-- Credenciales: actualizar solo el hash a partir de contraseña en claro (bcrypt)
-- Requiere extensión pgcrypto (credenciales/create_plain.sql la crea antes).
-- Ejemplo:
--   SELECT credenciales_update_password_plain(31, 'MiNuevaClave12');
-- =============================================================================

CREATE OR REPLACE FUNCTION credenciales_update_password_plain(
  p_id_credencial INTEGER,
  p_contrasena_plano TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
  v_plain TEXT;
BEGIN
  v_plain := trim(p_contrasena_plano);
  IF v_plain IS NULL OR char_length(v_plain) < 6 THEN
    RAISE EXCEPTION 'credenciales_update_password_plain: la contraseña debe tener al menos 6 caracteres'
      USING ERRCODE = '23514';
  END IF;

  UPDATE "Credenciales"
  SET "HashContrasena" = crypt(v_plain, gen_salt('bf', 12))
  WHERE "IdCredencial" = p_id_credencial;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'credenciales_update_password_plain: no existe credencial con IdCredencial = %', p_id_credencial
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' OR SQLSTATE = '23514' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'credenciales_update_password_plain: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION credenciales_update_password_plain(INTEGER, TEXT) IS 'Reemplaza HashContrasena por bcrypt de la contraseña en texto plano.';
