-- =============================================================================
-- Proveedores: DELETE
-- Nota: no eliminar si existen citas para este proveedor (FK "IdProveedor").
-- =============================================================================

CREATE OR REPLACE FUNCTION proveedores_delete(p_id_nit NUMERIC(9, 0))
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM "Proveedores"
  WHERE "IdNit" = p_id_nit;

  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  IF v_deleted = 0 THEN
    RAISE EXCEPTION 'proveedores_delete: no existe proveedor con IdNit = %', p_id_nit
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'proveedores_delete: hay citas u otros registros dependientes -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'proveedores_delete: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION proveedores_delete(NUMERIC) IS 'Elimina un proveedor por "IdNit".';
