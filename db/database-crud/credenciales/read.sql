-- =============================================================================
-- Credenciales: SELECT (Read)
-- =============================================================================

CREATE OR REPLACE FUNCTION credenciales_get_all()
RETURNS TABLE(
  id_credencial INTEGER,
  correo VARCHAR(255),
  hash_contrasena VARCHAR(255)
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT c."IdCredencial", c."Correo", c."HashContrasena"
  FROM "Credenciales" c
  ORDER BY c."IdCredencial";
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'credenciales_get_all: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

CREATE OR REPLACE FUNCTION credenciales_get_by_id(p_id_credencial INTEGER)
RETURNS TABLE(
  id_credencial INTEGER,
  correo VARCHAR(255),
  hash_contrasena VARCHAR(255)
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "Credenciales" c WHERE c."IdCredencial" = p_id_credencial) THEN
    RAISE EXCEPTION 'credenciales_get_by_id: no existe credencial con IdCredencial = %', p_id_credencial
      USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT c."IdCredencial", c."Correo", c."HashContrasena"
  FROM "Credenciales" c
  WHERE c."IdCredencial" = p_id_credencial;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'credenciales_get_by_id: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION credenciales_get_all() IS 'Lista todas las credenciales.';
COMMENT ON FUNCTION credenciales_get_by_id(INTEGER) IS 'Obtiene una credencial por "IdCredencial".';
