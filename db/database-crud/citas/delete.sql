-- =============================================================================
-- Citas: DELETE
-- Puede fallar por FK desde "HistorialCambios" o por triggers de auditoría,
-- según el orden y reglas de integridad en tu base.
-- =============================================================================

CREATE OR REPLACE FUNCTION citas_delete(p_id INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM "Citas"
  WHERE "Id" = p_id;

  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  IF v_deleted = 0 THEN
    RAISE EXCEPTION 'citas_delete: no existe cita con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'citas_delete: hay registros dependientes (historial, etc.) -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'citas_delete: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION citas_delete(INTEGER) IS 'Elimina una cita por "Id".';
