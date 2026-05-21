-- Permite franjas distintas por equipo de descarga en el mismo día y bodega.
-- Idempotente.

ALTER TABLE "FranjasPermitidasCitaFecha" DROP CONSTRAINT IF EXISTS "UqFranjaFechaBodegaOrden";
ALTER TABLE "FranjasPermitidasCitaFecha" DROP CONSTRAINT IF EXISTS "UqFranjaFechaOrden";

DROP INDEX IF EXISTS "UqFranjaFechaBodegaOrden";
DROP INDEX IF EXISTS "UqFranjaFechaOrden";
DROP INDEX IF EXISTS "UqFranjaFechaBodegaOrdenCompartido";
DROP INDEX IF EXISTS "UqFranjaFechaBodegaEquipoOrden";

CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaFechaBodegaOrdenCompartido"
  ON "FranjasPermitidasCitaFecha" ("Fecha", "IdBodega", "Orden")
  WHERE "IdEquipoDescargaBodega" IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaFechaBodegaEquipoOrden"
  ON "FranjasPermitidasCitaFecha" ("Fecha", "IdBodega", "IdEquipoDescargaBodega", "Orden")
  WHERE "IdEquipoDescargaBodega" IS NOT NULL;

COMMENT ON INDEX "UqFranjaFechaBodegaOrdenCompartido" IS
  'Franjas compartidas (sin equipo): una fila por Fecha+Bodega+Orden.';
COMMENT ON INDEX "UqFranjaFechaBodegaEquipoOrden" IS
  'Franjas por muelle: una fila por Fecha+Bodega+Equipo+Orden.';
