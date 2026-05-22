-- Integridad: citas y franjas deben usar equipos de la misma bodega.
-- Repara datos huérfanos y evita nuevas inconsistencias. Idempotente.

-- 1) Eliminar franjas por fecha con equipo de otra bodega o inactivo.
DELETE FROM "FranjasPermitidasCitaFecha" f
WHERE f."IdEquipoDescargaBodega" IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM "EquiposDescargaBodega" e
    WHERE e."Id" = f."IdEquipoDescargaBodega"
      AND e."IdBodega" = f."IdBodega"
      AND e."Activo" = TRUE
  );

-- 2) Eliminar franjas semanales con equipo ajeno o inactivo.
DELETE FROM "FranjasPermitidasCita" f
WHERE f."IdEquipoDescargaBodega" IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM "EquiposDescargaBodega" e
    WHERE e."Id" = f."IdEquipoDescargaBodega"
      AND e."IdBodega" = f."IdBodega"
      AND e."Activo" = TRUE
  );

-- 3) Citas con equipo inválido → primer muelle activo de la bodega.
UPDATE "Citas" c
SET "IdEquipoDescargaBodega" = (
  SELECT e."Id"
  FROM "EquiposDescargaBodega" e
  WHERE e."IdBodega" = c."IdBodega" AND e."Activo" = TRUE
  ORDER BY e."Orden", e."Id"
  LIMIT 1
)
WHERE c."IdEquipoDescargaBodega" IS NULL
   OR NOT EXISTS (
     SELECT 1 FROM "EquiposDescargaBodega" e
     WHERE e."Id" = c."IdEquipoDescargaBodega"
       AND e."IdBodega" = c."IdBodega"
       AND e."Activo" = TRUE
   );

-- 4) Franjas semanales sin equipo → primer muelle (solo si no rompe unicidad).
UPDATE "FranjasPermitidasCita" f
SET "IdEquipoDescargaBodega" = pick."Id"
FROM (
  SELECT f2."Id" AS fid, e."Id"
  FROM "FranjasPermitidasCita" f2
  JOIN LATERAL (
    SELECT e2."Id"
    FROM "EquiposDescargaBodega" e2
    WHERE e2."IdBodega" = f2."IdBodega" AND e2."Activo" = TRUE
    ORDER BY e2."Orden", e2."Id"
    LIMIT 1
  ) e ON TRUE
  WHERE f2."IdEquipoDescargaBodega" IS NULL
) pick
WHERE f."Id" = pick.fid
  AND NOT EXISTS (
    SELECT 1 FROM "FranjasPermitidasCita" dup
    WHERE dup."IdBodega" = f."IdBodega"
      AND dup."IdEquipoDescargaBodega" = pick."Id"
      AND dup."Orden" = f."Orden"
      AND dup."Id" <> f."Id"
  );

-- 5) Franjas por fecha sin equipo → primer muelle (solo si no hay duplicado).
UPDATE "FranjasPermitidasCitaFecha" f
SET "IdEquipoDescargaBodega" = pick."Id"
FROM (
  SELECT f2."Id" AS fid, e."Id"
  FROM "FranjasPermitidasCitaFecha" f2
  JOIN LATERAL (
    SELECT e2."Id"
    FROM "EquiposDescargaBodega" e2
    WHERE e2."IdBodega" = f2."IdBodega" AND e2."Activo" = TRUE
    ORDER BY e2."Orden", e2."Id"
    LIMIT 1
  ) e ON TRUE
  WHERE f2."IdEquipoDescargaBodega" IS NULL
) pick
WHERE f."Id" = pick.fid
  AND NOT EXISTS (
    SELECT 1 FROM "FranjasPermitidasCitaFecha" dup
    WHERE dup."Fecha" = f."Fecha"
      AND dup."IdBodega" = f."IdBodega"
      AND dup."IdEquipoDescargaBodega" = pick."Id"
      AND dup."Orden" = f."Orden"
      AND dup."Id" <> f."Id"
  );

-- 6) Borrar franjas por fecha huérfanas que no se pudieron asignar sin duplicar.
DELETE FROM "FranjasPermitidasCitaFecha" f
WHERE f."IdEquipoDescargaBodega" IS NULL;

CREATE OR REPLACE FUNCTION "FnCitaEquipoMismaBodega"()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  eq_bodega INTEGER;
BEGIN
  IF NEW."IdEquipoDescargaBodega" IS NULL THEN
    RETURN NEW;
  END IF;
  SELECT e."IdBodega" INTO eq_bodega
  FROM "EquiposDescargaBodega" e
  WHERE e."Id" = NEW."IdEquipoDescargaBodega" AND e."Activo" = TRUE;
  IF eq_bodega IS NULL OR eq_bodega <> NEW."IdBodega" THEN
    RAISE EXCEPTION 'El equipo de descarga no pertenece a la bodega de la cita (IdBodega=%)', NEW."IdBodega"
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS "TrgCitaEquipoMismaBodega" ON "Citas";
CREATE TRIGGER "TrgCitaEquipoMismaBodega"
  BEFORE INSERT OR UPDATE OF "IdBodega", "IdEquipoDescargaBodega" ON "Citas"
  FOR EACH ROW
  EXECUTE FUNCTION "FnCitaEquipoMismaBodega"();

COMMENT ON FUNCTION "FnCitaEquipoMismaBodega"() IS
  'Impide citas con IdEquipoDescargaBodega de otra bodega o inactivo.';
