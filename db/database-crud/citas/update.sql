-- =============================================================================
-- Citas: UPDATE
-- Si existe trigger de auditoría (002_audit_triggers.sql), cada UPDATE puede
-- generar filas en "HistorialCambios".
-- =============================================================================

CREATE OR REPLACE FUNCTION citas_update(
  p_id INTEGER,
  p_id_proveedor NUMERIC(9, 0),
  p_descripcion_material TEXT,
  p_fecha_hora_inicio TIMESTAMPTZ,
  p_duracion_minutos INTEGER,
  p_estado VARCHAR
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
  v_estado "EstadoCita";
BEGIN
  v_estado := p_estado::"EstadoCita";

  UPDATE "Citas"
  SET
    "IdProveedor" = p_id_proveedor,
    "DescripcionMaterial" = p_descripcion_material,
    "FechaHoraInicio" = p_fecha_hora_inicio,
    "DuracionMinutos" = p_duracion_minutos,
    "Estado" = v_estado
  WHERE "Id" = p_id;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'citas_update: no existe cita con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN invalid_text_representation THEN
    RAISE EXCEPTION 'citas_update: estado inválido "%"', p_estado
      USING ERRCODE = '22P02';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'citas_update: IdProveedor inválido -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN check_violation THEN
    RAISE EXCEPTION 'citas_update: validación CHECK -> %', SQLERRM
      USING ERRCODE = '23514';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'citas_update: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION citas_update(INTEGER, NUMERIC, TEXT, TIMESTAMPTZ, INTEGER, VARCHAR) IS 'Actualiza una cita por "Id".';
