-- =============================================================================
-- HistorialCambios: SELECT (Read)
-- =============================================================================

CREATE OR REPLACE FUNCTION historial_cambios_get_all()
RETURNS TABLE(
  id INTEGER,
  id_actor VARCHAR(30),
  id_cita INTEGER,
  accion VARCHAR(80),
  descripcion TEXT,
  creado_en TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    h."Id",
    h."IdActor",
    h."IdCita",
    h."Accion",
    h."Descripcion",
    h."CreadoEn"
  FROM "HistorialCambios" h
  ORDER BY h."CreadoEn" DESC, h."Id" DESC;
EXCEPTION
  WHEN OTHERS THEN
    RAISE EXCEPTION 'historial_cambios_get_all: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

CREATE OR REPLACE FUNCTION historial_cambios_get_by_id(p_id INTEGER)
RETURNS TABLE(
  id INTEGER,
  id_actor VARCHAR(30),
  id_cita INTEGER,
  accion VARCHAR(80),
  descripcion TEXT,
  creado_en TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM "HistorialCambios" h WHERE h."Id" = p_id) THEN
    RAISE EXCEPTION 'historial_cambios_get_by_id: no existe registro con Id = %', p_id
      USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT
    h."Id",
    h."IdActor",
    h."IdCita",
    h."Accion",
    h."Descripcion",
    h."CreadoEn"
  FROM "HistorialCambios" h
  WHERE h."Id" = p_id;
EXCEPTION
  WHEN OTHERS THEN
    IF SQLSTATE = 'P0002' THEN
      RAISE;
    END IF;
    RAISE EXCEPTION 'historial_cambios_get_by_id: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION historial_cambios_get_all() IS 'Lista todo el historial de cambios.';
COMMENT ON FUNCTION historial_cambios_get_by_id(INTEGER) IS 'Obtiene un registro de historial por "Id".';
