-- =============================================================================
-- Proveedores: UPDATE
-- "IdNit" (PK) no se modifica.
-- Migra firma antigua (6 args) a la actual (7 args, incluye correo empresa).
-- =============================================================================

DROP FUNCTION IF EXISTS proveedores_update(numeric, varchar, varchar, varchar, integer, varchar, varchar);
DROP FUNCTION IF EXISTS proveedores_update(numeric, varchar, varchar, integer, varchar, varchar);

CREATE OR REPLACE FUNCTION proveedores_update(
  p_id_nit NUMERIC(9, 0),
  p_digito_verificacion VARCHAR(1),
  p_nombre_empresa VARCHAR(160),
  p_correo_empresa VARCHAR(255),
  p_id_credencial INTEGER,
  p_nombre_persona_responsable VARCHAR(160),
  p_documento_persona_responsable VARCHAR(30)
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
BEGIN
  UPDATE "Proveedores"
  SET
    "DigitoVerificacion" = p_digito_verificacion,
    "NombreEmpresa" = p_nombre_empresa,
    "CorreoEmpresa" = p_correo_empresa,
    "IdCredencial" = p_id_credencial,
    "NombrePersonaResponsable" = p_nombre_persona_responsable,
    "DocumentoPersonaResponsable" = p_documento_persona_responsable
  WHERE "IdNit" = p_id_nit;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'proveedores_update: no existe proveedor con IdNit = %', p_id_nit
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'proveedores_update: conflicto de unicidad -> %', SQLERRM
      USING ERRCODE = '23505';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'proveedores_update: IdCredencial inválido -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN check_violation THEN
    RAISE EXCEPTION 'proveedores_update: validación CHECK -> %', SQLERRM
      USING ERRCODE = '23514';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'proveedores_update: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION proveedores_update(NUMERIC, VARCHAR, VARCHAR, VARCHAR, INTEGER, VARCHAR, VARCHAR) IS 'Actualiza un proveedor por NIT.';
