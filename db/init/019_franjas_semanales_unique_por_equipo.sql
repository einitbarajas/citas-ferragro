-- Franjas semanales distintas por equipo de descarga en la misma bodega.
-- Idempotente.

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
