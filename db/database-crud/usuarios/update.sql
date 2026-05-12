-- =============================================================================
-- Usuarios: UPDATE
-- La PK "IdDocumento" no se modifica; use eliminar + crear si necesita cambiarla.
-- =============================================================================

CREATE OR REPLACE FUNCTION usuarios_update(
  p_id_documento VARCHAR(30),
  p_nombre_completo VARCHAR(120),
  p_id_credencial INTEGER,
  p_id_rol INTEGER
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
BEGIN
  UPDATE "Usuarios"
  SET
    "NombreCompleto" = p_nombre_completo,
    "IdCredencial" = p_id_credencial,
    "IdRol" = p_id_rol
  WHERE "IdDocumento" = p_id_documento;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'usuarios_update: no existe usuario con IdDocumento = %', p_id_documento
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'usuarios_update: credencial duplicada u otro conflicto de unicidad -> %', SQLERRM
      USING ERRCODE = '23505';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'usuarios_update: IdCredencial o IdRol inválido -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN check_violation THEN
    RAISE EXCEPTION 'usuarios_update: validación CHECK fallida -> %', SQLERRM
      USING ERRCODE = '23514';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'usuarios_update: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION usuarios_update(VARCHAR, VARCHAR, INTEGER, INTEGER) IS 'Actualiza datos de un usuario por documento.';
