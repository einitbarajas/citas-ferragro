-- =============================================================================
-- Citas: INSERT (Create)
-- p_estado: valores del ENUM "EstadoCita" ('sin_revision', 'revisado', 'cancelado').
-- Si aplica db/init/002_audit_triggers.sql, el AFTER INSERT puede insertar en "HistorialCambios".
-- =============================================================================

CREATE OR REPLACE FUNCTION citas_create(
  p_id_proveedor NUMERIC(9, 0),
  p_descripcion_material TEXT,
  p_fecha_hora_inicio TIMESTAMPTZ,
  p_duracion_minutos INTEGER DEFAULT 90,
  p_estado VARCHAR DEFAULT 'sin_revision'
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_id INTEGER;
  v_estado "EstadoCita";
BEGIN
  v_estado := p_estado::"EstadoCita";

  INSERT INTO "Citas" (
    "IdProveedor",
    "DescripcionMaterial",
    "FechaHoraInicio",
    "DuracionMinutos",
    "Estado"
  )
  VALUES (
    p_id_proveedor,
    p_descripcion_material,
    p_fecha_hora_inicio,
    p_duracion_minutos,
    v_estado
  )
  RETURNING "Id" INTO v_id;

  RETURN v_id;
EXCEPTION
  WHEN invalid_text_representation THEN
    RAISE EXCEPTION 'citas_create: estado inválido "%" (use sin_revision, revisado o cancelado)', p_estado
      USING ERRCODE = '22P02';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'citas_create: IdProveedor no existe en "Proveedores" -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN check_violation THEN
    RAISE EXCEPTION 'citas_create: validación CHECK -> %', SQLERRM
      USING ERRCODE = '23514';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'citas_create: %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'citas_create: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION citas_create(NUMERIC, TEXT, TIMESTAMPTZ, INTEGER, VARCHAR) IS 'Inserta una cita y devuelve "Id".';
