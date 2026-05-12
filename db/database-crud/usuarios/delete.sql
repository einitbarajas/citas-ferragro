-- =============================================================================
-- Usuarios: DELETE
-- Nota: no eliminar si "HistorialCambios" referencia "IdActor" = este documento.
-- =============================================================================

CREATE OR REPLACE FUNCTION usuarios_delete(p_id_documento VARCHAR(30))
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted INTEGER;
BEGIN
  DELETE FROM "Usuarios"
  WHERE "IdDocumento" = p_id_documento;

  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  IF v_deleted = 0 THEN
    RAISE EXCEPTION 'usuarios_delete: no existe usuario con IdDocumento = %', p_id_documento
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'usuarios_delete: hay registros dependientes (p. ej. historial de cambios) -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'usuarios_delete: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION usuarios_delete(VARCHAR) IS 'Elimina un usuario por "IdDocumento".';
