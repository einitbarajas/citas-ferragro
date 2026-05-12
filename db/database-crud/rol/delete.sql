-- =============================================================================
-- Rol: DELETE
-- Nota: fallará si existen "Usuarios" que referencian este rol (FK).
-- =============================================================================

CREATE OR REPLACE FUNCTION rol_delete(p_id INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM "Rol"
  WHERE "Id" = p_id;

  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  IF v_deleted = 0 THEN
    RAISE EXCEPTION 'rol_delete: no existe rol con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'rol_delete: no se puede eliminar; hay registros dependientes -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'rol_delete: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION rol_delete(INTEGER) IS 'Elimina un rol por "Id".';
