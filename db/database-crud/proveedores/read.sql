-- =============================================================================
-- Proveedores: SELECT (Read)
-- Si cambia RETURNS TABLE, hay que DROP antes (CREATE OR REPLACE no altera OUT).
-- =============================================================================

DROP FUNCTION IF EXISTS proveedores_get_all();
DROP FUNCTION IF EXISTS proveedores_get_by_id(numeric);

CREATE OR REPLACE FUNCTION proveedores_get_all()
RETURNS TABLE(
  id_nit NUMERIC(9, 0),
  digito_verificacion VARCHAR(1),
  nombre_empresa VARCHAR(160),
  correo_empresa VARCHAR(255),
  id_credencial INTEGER,
  nombre_persona_responsable VARCHAR(160),
  documento_persona_responsable VARCHAR(30)
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    p."IdNit",
    p."DigitoVerificacion",
    p."NombreEmpresa",
    p."CorreoEmpresa",
    p."IdCredencial",
    p."NombrePersonaResponsable",
    p."DocumentoPersonaResponsable"
  FROM "Proveedores" p
  ORDER BY p."IdNit";
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'proveedores_get_all: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

CREATE OR REPLACE FUNCTION proveedores_get_by_id(p_id_nit NUMERIC(9, 0))
RETURNS TABLE(
  id_nit NUMERIC(9, 0),
  digito_verificacion VARCHAR(1),
  nombre_empresa VARCHAR(160),
  correo_empresa VARCHAR(255),
  id_credencial INTEGER,
  nombre_persona_responsable VARCHAR(160),
  documento_persona_responsable VARCHAR(30)
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "Proveedores" p WHERE p."IdNit" = p_id_nit) THEN
    RAISE EXCEPTION 'proveedores_get_by_id: no existe proveedor con IdNit = %', p_id_nit
      USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT
    p."IdNit",
    p."DigitoVerificacion",
    p."NombreEmpresa",
    p."CorreoEmpresa",
    p."IdCredencial",
    p."NombrePersonaResponsable",
    p."DocumentoPersonaResponsable"
  FROM "Proveedores" p
  WHERE p."IdNit" = p_id_nit;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'proveedores_get_by_id: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION proveedores_get_all() IS 'Lista todos los proveedores.';
COMMENT ON FUNCTION proveedores_get_by_id(NUMERIC) IS 'Obtiene un proveedor por NIT (PK).';
