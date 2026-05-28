-- Franjas semanales distintas por equipo de descarga en la misma bodega.
-- Idempotente.

-- Quitar duplicados legacy (misma Bodega+Equipo+Orden) antes de los índices únicos.
DELETE FROM "FranjasPermitidasCita" f
WHERE f."IdEquipoDescargaBodega" IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM "FranjasPermitidasCita" keep
    WHERE keep."IdBodega" = f."IdBodega"
      AND keep."IdEquipoDescargaBodega" = f."IdEquipoDescargaBodega"
      AND keep."Orden" = f."Orden"
      AND keep."Id" < f."Id"
  );

DELETE FROM "FranjasPermitidasCita" f
WHERE f."IdEquipoDescargaBodega" IS NULL
  AND EXISTS (
    SELECT 1
    FROM "FranjasPermitidasCita" keep
    WHERE keep."IdBodega" = f."IdBodega"
      AND keep."IdEquipoDescargaBodega" IS NULL
      AND keep."Orden" = f."Orden"
      AND keep."Id" < f."Id"
  );

ALTER TABLE "FranjasPermitidasCita" DROP CONSTRAINT IF EXISTS "UqFranjaBodegaOrden";
ALTER TABLE "FranjasPermitidasCita" DROP CONSTRAINT IF EXISTS "UqFranjaOrden";

DROP INDEX IF EXISTS "UqFranjaBodegaOrden";
DROP INDEX IF EXISTS "UqFranjaOrden";
DROP INDEX IF EXISTS "UqFranjaBodegaOrdenCompartido";
DROP INDEX IF EXISTS "UqFranjaBodegaEquipoOrden";

CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaBodegaOrdenCompartido"
  ON "FranjasPermitidasCita" ("IdBodega", "Orden")
  WHERE "IdEquipoDescargaBodega" IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaBodegaEquipoOrden"
  ON "FranjasPermitidasCita" ("IdBodega", "IdEquipoDescargaBodega", "Orden")
  WHERE "IdEquipoDescargaBodega" IS NOT NULL;

COMMENT ON INDEX "UqFranjaBodegaOrdenCompartido" IS
  'Franjas semanales compartidas (sin equipo): una fila por Bodega+Orden.';
COMMENT ON INDEX "UqFranjaBodegaEquipoOrden" IS
  'Franjas semanales por muelle: una fila por Bodega+Equipo+Orden.';
