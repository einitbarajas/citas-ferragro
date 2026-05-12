-- =============================================================================
-- Rol: SELECT (Read) — listado completo y por identificador.
-- =============================================================================

CREATE OR REPLACE FUNCTION rol_get_all()
RETURNS TABLE(id INTEGER, nombre VARCHAR(40))
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT r."Id", r."Nombre"
  FROM "Rol" r
  ORDER BY r."Id";
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'rol_get_all: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

CREATE OR REPLACE FUNCTION rol_get_by_id(p_id INTEGER)
RETURNS TABLE(id INTEGER, nombre VARCHAR(40))
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "Rol" r WHERE r."Id" = p_id) THEN
    RAISE EXCEPTION 'rol_get_by_id: no existe rol con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT r."Id", r."Nombre"
  FROM "Rol" r
  WHERE r."Id" = p_id;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'rol_get_by_id: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION rol_get_all() IS 'Devuelve todos los registros de "Rol".';
COMMENT ON FUNCTION rol_get_by_id(INTEGER) IS 'Devuelve un rol por "Id"; lanza error si no existe.';
