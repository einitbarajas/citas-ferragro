-- =============================================================================
-- Credenciales: INSERT (Create)
-- p_hash_contrasena debe ser un hash bcrypt (como genera el API). Para pasar
-- la contraseña en claro desde SQL, use credenciales_create_plain (create_plain.sql).
-- =============================================================================

CREATE OR REPLACE FUNCTION credenciales_create(
  p_correo VARCHAR(255),
  p_hash_contrasena VARCHAR(255)
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_id INTEGER;
BEGIN
  INSERT INTO "Credenciales" ("Correo", "HashContrasena")
  VALUES (p_correo, p_hash_contrasena)
  RETURNING "IdCredencial" INTO v_id;

  RETURN v_id;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'credenciales_create: el correo "%" ya está registrado', p_correo
      USING ERRCODE = '23505';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'credenciales_create: %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'credenciales_create: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION credenciales_create(VARCHAR, VARCHAR) IS 'Inserta credenciales y devuelve "IdCredencial".';
