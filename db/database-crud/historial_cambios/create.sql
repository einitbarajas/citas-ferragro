-- =============================================================================
-- HistorialCambios: INSERT (Create)
-- "IdActor": documento de Usuarios o IdProveedor como texto (sin FK).
-- "CreadoEn": si p_creado_en es NULL se usa NOW().
-- =============================================================================

CREATE OR REPLACE FUNCTION historial_cambios_create(
  p_id_actor VARCHAR(30),
  p_id_cita INTEGER,
  p_accion VARCHAR(80),
  p_descripcion TEXT,
  p_creado_en TIMESTAMPTZ DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_id INTEGER;
BEGIN
  INSERT INTO "HistorialCambios" (
    "IdActor",
    "IdCita",
    "Accion",
    "Descripcion",
    "CreadoEn"
  )
  VALUES (
    p_id_actor,
    p_id_cita,
    p_accion,
    p_descripcion,
    COALESCE(p_creado_en, NOW())
  )
  RETURNING "Id" INTO v_id;

  RETURN v_id;
EXCEPTION
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'historial_cambios_create: IdCita inválido o cita inexistente -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'historial_cambios_create: %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'historial_cambios_create: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION historial_cambios_create(VARCHAR, INTEGER, VARCHAR, TEXT, TIMESTAMPTZ) IS 'Inserta un registro de auditoría y devuelve "Id".';
