-- =============================================================================
-- Credenciales: DELETE
-- Nota: no eliminar si "Usuarios" o "Proveedores" referencian IdCredencial.
-- =============================================================================

CREATE OR REPLACE FUNCTION credenciales_delete(p_id_credencial INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM "Credenciales"
  WHERE "IdCredencial" = p_id_credencial;

  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  IF v_deleted = 0 THEN
    RAISE EXCEPTION 'credenciales_delete: no existe credencial con IdCredencial = %', p_id_credencial
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'credenciales_delete: hay usuarios o proveedores usando esta credencial -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'credenciales_delete: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION credenciales_delete(INTEGER) IS 'Elimina credenciales por "IdCredencial".';
