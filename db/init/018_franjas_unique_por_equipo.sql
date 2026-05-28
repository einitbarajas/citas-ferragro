-- Permite franjas distintas por equipo de descarga en el mismo día y bodega.
-- Idempotente.

-- Quitar duplicados legacy (misma Fecha+Bodega+Equipo+Orden) antes de los índices únicos.
DELETE FROM "FranjasPermitidasCitaFecha" f
WHERE f."IdEquipoDescargaBodega" IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM "FranjasPermitidasCitaFecha" keep
    WHERE keep."Fecha" = f."Fecha"
      AND keep."IdBodega" = f."IdBodega"
      AND keep."IdEquipoDescargaBodega" = f."IdEquipoDescargaBodega"
      AND keep."Orden" = f."Orden"
      AND keep."Id" < f."Id"
  );

DELETE FROM "FranjasPermitidasCitaFecha" f
WHERE f."IdEquipoDescargaBodega" IS NULL
  AND EXISTS (
    SELECT 1
    FROM "FranjasPermitidasCitaFecha" keep
    WHERE keep."Fecha" = f."Fecha"
      AND keep."IdBodega" = f."IdBodega"
      AND keep."IdEquipoDescargaBodega" IS NULL
      AND keep."Orden" = f."Orden"
      AND keep."Id" < f."Id"
  );

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
