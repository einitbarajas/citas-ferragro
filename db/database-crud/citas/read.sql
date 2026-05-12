-- =============================================================================
-- Citas: SELECT (Read)
-- =============================================================================

CREATE OR REPLACE FUNCTION citas_get_all()
RETURNS TABLE(
  id INTEGER,
  id_proveedor NUMERIC(9, 0),
  descripcion_material TEXT,
  fecha_hora_inicio TIMESTAMPTZ,
  duracion_minutos INTEGER,
  estado "EstadoCita"
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    c."Id",
    c."IdProveedor",
    c."DescripcionMaterial",
    c."FechaHoraInicio",
    c."DuracionMinutos",
    c."Estado"
  FROM "Citas" c
  ORDER BY c."FechaHoraInicio", c."Id";
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'citas_get_all: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

CREATE OR REPLACE FUNCTION citas_get_by_id(p_id INTEGER)
RETURNS TABLE(
  id INTEGER,
  id_proveedor NUMERIC(9, 0),
  descripcion_material TEXT,
  fecha_hora_inicio TIMESTAMPTZ,
  duracion_minutos INTEGER,
  estado "EstadoCita"
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "Citas" c WHERE c."Id" = p_id) THEN
    RAISE EXCEPTION 'citas_get_by_id: no existe cita con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT
    c."Id",
    c."IdProveedor",
    c."DescripcionMaterial",
    c."FechaHoraInicio",
    c."DuracionMinutos",
    c."Estado"
  FROM "Citas" c
  WHERE c."Id" = p_id;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'citas_get_by_id: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION citas_get_all() IS 'Lista todas las citas.';
COMMENT ON FUNCTION citas_get_by_id(INTEGER) IS 'Obtiene una cita por "Id".';
