-- =============================================================================
-- Rol: UPDATE
-- =============================================================================

CREATE OR REPLACE FUNCTION rol_update(p_id INTEGER, p_nombre VARCHAR(40))
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
BEGIN
  UPDATE "Rol"
  SET "Nombre" = p_nombre
  WHERE "Id" = p_id;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'rol_update: no existe rol con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'rol_update: ya existe otro rol con el nombre "%"', p_nombre
      USING ERRCODE = '23505';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'rol_update: violación de clave foránea -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'rol_update: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION rol_update(INTEGER, VARCHAR) IS 'Actualiza "Nombre" del rol identificado por "Id".';
