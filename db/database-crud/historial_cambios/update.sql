-- =============================================================================
-- HistorialCambios: UPDATE
-- ADVERTENCIA: si aplicaste db/init/002_audit_triggers.sql, los triggers
-- "TrgBloquearUpdateHistorial" impiden cualquier UPDATE en esta tabla.
-- Esta función intentará el UPDATE y propagará el error con contexto.
-- =============================================================================

CREATE OR REPLACE FUNCTION historial_cambios_update(
  p_id INTEGER,
  p_id_actor VARCHAR(30),
  p_id_cita INTEGER,
  p_accion VARCHAR(80),
  p_descripcion TEXT,
  p_creado_en TIMESTAMPTZ
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_updated INTEGER;
BEGIN
  UPDATE "HistorialCambios"
  SET
    "IdActor" = p_id_actor,
    "IdCita" = p_id_cita,
    "Accion" = p_accion,
    "Descripcion" = p_descripcion,
    "CreadoEn" = p_creado_en
  WHERE "Id" = p_id;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 0 THEN
    RAISE EXCEPTION 'historial_cambios_update: no existe registro con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'historial_cambios_update: IdActor o IdCita inválido -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    IF SQLERRM ILIKE '%inmutable%' THEN
      RAISE EXCEPTION 'historial_cambios_update: la tabla de historial es inmutable por política (trigger). Original: %', SQLERRM
        USING ERRCODE = 'P0001';
    END IF;
    RAISE EXCEPTION 'historial_cambios_update: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION historial_cambios_update(INTEGER, VARCHAR, INTEGER, VARCHAR, TEXT, TIMESTAMPTZ) IS 'Intenta actualizar un registro de historial (bloqueado si hay triggers de inmutabilidad).';
