-- =============================================================================
-- Credenciales: UPDATE
-- =============================================================================

CREATE OR REPLACE FUNCTION credenciales_update(
  p_id_credencial INTEGER,
  p_correo VARCHAR(255),
  p_hash_contrasena VARCHAR(255)
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
BEGIN
  UPDATE "Credenciales"
  SET
    "Correo" = p_correo,
    "HashContrasena" = p_hash_contrasena
  WHERE "IdCredencial" = p_id_credencial;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'credenciales_update: no existe credencial con IdCredencial = %', p_id_credencial
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'credenciales_update: el correo "%" ya está en uso', p_correo
      USING ERRCODE = '23505';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'credenciales_update: violación de clave foránea -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'credenciales_update: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION credenciales_update(INTEGER, VARCHAR, VARCHAR) IS 'Actualiza correo y hash de una credencial.';
