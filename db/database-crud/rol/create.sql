-- =============================================================================
-- Rol: INSERT (Create)
-- Requiere: db/init/001_schema.sql aplicado previamente.
-- =============================================================================

CREATE OR REPLACE FUNCTION rol_create(p_nombre VARCHAR(40))
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_id INTEGER;
BEGIN
  INSERT INTO "Rol" ("Nombre")
  VALUES (p_nombre)
  RETURNING "Id" INTO v_id;

  RETURN v_id;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'rol_create: ya existe un rol con el nombre "%" (unicidad en "Nombre")', p_nombre
      USING ERRCODE = '23505';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'rol_create: campo obligatorio faltante -> %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'rol_create: error inesperado [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION rol_create(VARCHAR) IS 'Inserta un registro en "Rol" y devuelve el "Id" generado.';
