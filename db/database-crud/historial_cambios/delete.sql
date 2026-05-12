-- =============================================================================
-- HistorialCambios: DELETE
-- ADVERTENCIA: con db/init/002_audit_triggers.sql el DELETE está bloqueado
-- por el trigger "TrgBloquearDeleteHistorial".
-- =============================================================================

CREATE OR REPLACE FUNCTION historial_cambios_delete(p_id INTEGER)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM "HistorialCambios"
  WHERE "Id" = p_id;

  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  IF v_deleted = 0 THEN
    RAISE EXCEPTION 'historial_cambios_delete: no existe registro con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    IF SQLERRM ILIKE '%inmutable%' THEN
      RAISE EXCEPTION 'historial_cambios_delete: la tabla de historial es inmutable por política (trigger). Original: %', SQLERRM
        USING ERRCODE = 'P0001';
    END IF;
    RAISE EXCEPTION 'historial_cambios_delete: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION historial_cambios_delete(INTEGER) IS 'Intenta eliminar un registro de historial (bloqueado si hay triggers de inmutabilidad).';
