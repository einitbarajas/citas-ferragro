-- =============================================================================
-- Proveedores: INSERT (Create)
-- Migra firma antigua (6 args) a la actual (7 args, incluye correo empresa).
-- =============================================================================

DROP FUNCTION IF EXISTS proveedores_create(numeric, varchar, varchar, varchar, integer, varchar, varchar);
DROP FUNCTION IF EXISTS proveedores_create(numeric, varchar, varchar, integer, varchar, varchar);

CREATE OR REPLACE FUNCTION proveedores_create(
  p_id_nit NUMERIC(9, 0),
  p_digito_verificacion VARCHAR(1),
  p_nombre_empresa VARCHAR(160),
  p_correo_empresa VARCHAR(255),
  p_id_credencial INTEGER,
  p_nombre_persona_responsable VARCHAR(160),
  p_documento_persona_responsable VARCHAR(30)
)
RETURNS NUMERIC(9, 0)
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO "Proveedores" (
    "IdNit",
    "DigitoVerificacion",
    "NombreEmpresa",
    "CorreoEmpresa",
    "IdCredencial",
    "NombrePersonaResponsable",
    "DocumentoPersonaResponsable"
  )
  VALUES (
    p_id_nit,
    p_digito_verificacion,
    p_nombre_empresa,
    p_correo_empresa,
    p_id_credencial,
    p_nombre_persona_responsable,
    p_documento_persona_responsable
  );

  RETURN p_id_nit;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'proveedores_create: NIT o credencial duplicada -> %', SQLERRM
      USING ERRCODE = '23505';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'proveedores_create: IdCredencial inválido -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN check_violation THEN
    RAISE EXCEPTION 'proveedores_create: validación CHECK (DV o documento) -> %', SQLERRM
      USING ERRCODE = '23514';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'proveedores_create: %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'proveedores_create: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION proveedores_create(NUMERIC, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR) IS 'Inserta un proveedor y devuelve "IdNit".';
