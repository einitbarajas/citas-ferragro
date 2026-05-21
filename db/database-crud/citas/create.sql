-- =============================================================================
-- Citas: INSERT (Create)
-- p_estado: valores del ENUM "EstadoCita" ('sin_revision', 'revisado', 'cancelado').
-- Si aplica db/init/002_audit_triggers.sql, el AFTER INSERT puede insertar en "HistorialCambios".
-- =============================================================================

DROP FUNCTION IF EXISTS citas_create(NUMERIC, TEXT, TIMESTAMPTZ, INTEGER, VARCHAR);
DROP FUNCTION IF EXISTS citas_create(NUMERIC, TEXT, TIMESTAMPTZ, INTEGER, VARCHAR, INTEGER);

CREATE OR REPLACE FUNCTION citas_create(
  p_id_proveedor NUMERIC(9, 0),
  p_descripcion_material TEXT,
  p_fecha_hora_inicio TIMESTAMPTZ,
  p_duracion_minutos INTEGER DEFAULT 90,
  p_estado VARCHAR DEFAULT 'sin_revision',
  p_id_bodega INTEGER DEFAULT NULL,
  p_id_equipo_descarga INTEGER DEFAULT NULL,
  p_indice_equipo_proveedor INTEGER DEFAULT 1
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_id INTEGER;
  v_estado "EstadoCita";
  v_id_bodega INTEGER;
  v_id_equipo INTEGER;
BEGIN
  v_estado := p_estado::"EstadoCita";

  v_id_bodega := p_id_bodega;
  IF v_id_bodega IS NULL THEN
    SELECT MIN(b."Id") INTO v_id_bodega
    FROM "Bodegas" b
    WHERE b."Activa" = TRUE;
  END IF;
  IF v_id_bodega IS NULL THEN
    SELECT MIN(b."Id") INTO v_id_bodega FROM "Bodegas" b;
  END IF;
  IF v_id_bodega IS NULL THEN
    RAISE EXCEPTION 'citas_create: no hay bodegas registradas; ejecute db/init/014_bodegas_franjas_flexibles.sql'
      USING ERRCODE = 'P0001';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM "Bodegas" b WHERE b."Id" = v_id_bodega) THEN
    RAISE EXCEPTION 'citas_create: IdBodega % no existe en "Bodegas"', v_id_bodega
      USING ERRCODE = '23503';
  END IF;

  v_id_equipo := p_id_equipo_descarga;
  IF v_id_equipo IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM "EquiposDescargaBodega" e
      WHERE e."Id" = v_id_equipo AND e."IdBodega" = v_id_bodega AND e."Activo" = TRUE
    ) THEN
      RAISE EXCEPTION 'citas_create: IdEquipoDescargaBodega % no pertenece a la bodega % o no está activo',
        v_id_equipo, v_id_bodega
        USING ERRCODE = '23503';
    END IF;
  ELSE
    SELECT e."Id" INTO v_id_equipo
    FROM "EquiposDescargaBodega" e
    WHERE e."IdBodega" = v_id_bodega AND e."Activo" = TRUE
    ORDER BY e."Orden", e."Id"
    LIMIT 1;
    IF v_id_equipo IS NULL THEN
      INSERT INTO "EquiposDescargaBodega" ("IdBodega", "Nombre", "Activo", "Orden")
      VALUES (v_id_bodega, 'Equipo 1', TRUE, 0)
      RETURNING "Id" INTO v_id_equipo;
    END IF;
  END IF;

  INSERT INTO "Citas" (
    "IdProveedor",
    "IdBodega",
    "IdEquipoDescargaBodega",
    "IndiceEquipoProveedor",
    "DescripcionMaterial",
    "FechaHoraInicio",
    "DuracionMinutos",
    "Estado"
  )
  VALUES (
    p_id_proveedor,
    v_id_bodega,
    v_id_equipo,
    GREATEST(1, LEAST(COALESCE(p_indice_equipo_proveedor, 1), 20)),
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

COMMENT ON FUNCTION citas_create(NUMERIC, TEXT, TIMESTAMPTZ, INTEGER, VARCHAR, INTEGER, INTEGER, INTEGER) IS
  'Inserta una cita. Si p_id_bodega es NULL, usa la bodega activa de menor Id. Si p_id_equipo_descarga es NULL, usa el primer equipo activo de esa bodega.';
