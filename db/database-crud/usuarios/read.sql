-- =============================================================================
-- Usuarios: SELECT (Read)
-- =============================================================================

CREATE OR REPLACE FUNCTION usuarios_get_all()
RETURNS TABLE(
  id_documento VARCHAR(30),
  nombre_completo VARCHAR(120),
  id_credencial INTEGER,
  id_rol INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    u."IdDocumento",
    u."NombreCompleto",
    u."IdCredencial",
    u."IdRol"
  FROM "Usuarios" u
  ORDER BY u."IdDocumento";
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'usuarios_get_all: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

CREATE OR REPLACE FUNCTION usuarios_get_by_id(p_id_documento VARCHAR(30))
RETURNS TABLE(
  id_documento VARCHAR(30),
  nombre_completo VARCHAR(120),
  id_credencial INTEGER,
  id_rol INTEGER
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "Usuarios" u WHERE u."IdDocumento" = p_id_documento) THEN
    RAISE EXCEPTION 'usuarios_get_by_id: no existe usuario con IdDocumento = %', p_id_documento
      USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT
    u."IdDocumento",
    u."NombreCompleto",
    u."IdCredencial",
    u."IdRol"
  FROM "Usuarios" u
  WHERE u."IdDocumento" = p_id_documento;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'usuarios_get_by_id: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION usuarios_get_all() IS 'Lista todos los usuarios internos.';
COMMENT ON FUNCTION usuarios_get_by_id(VARCHAR) IS 'Obtiene un usuario por documento (PK).';
