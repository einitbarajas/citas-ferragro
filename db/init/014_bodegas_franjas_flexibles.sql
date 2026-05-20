-- Bodegas (lugares de entrega) y franjas como turnos explícitos (inicio–fin con duración variable).
-- Idempotente: seguro re-ejecutar en bases existentes.

CREATE TABLE IF NOT EXISTS "Bodegas" (
  "Id" SERIAL PRIMARY KEY,
  "Nombre" VARCHAR(120) NOT NULL,
  "Direccion" VARCHAR(255),
  "Activa" BOOLEAN NOT NULL DEFAULT TRUE,
  "Orden" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "UqBodegasNombre" UNIQUE ("Nombre")
);

COMMENT ON TABLE "Bodegas" IS 'Lugares de entrega donde se agendan citas; cada bodega tiene sus propias franjas horarias.';

INSERT INTO "Bodegas" ("Nombre", "Direccion", "Activa", "Orden")
SELECT 'Bodega principal', NULL, TRUE, 0
WHERE NOT EXISTS (SELECT 1 FROM "Bodegas" LIMIT 1);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Citas' AND column_name = 'IdBodega'
  ) THEN
    ALTER TABLE "Citas" ADD COLUMN "IdBodega" INTEGER REFERENCES "Bodegas"("Id");
    UPDATE "Citas" SET "IdBodega" = (SELECT MIN("Id") FROM "Bodegas") WHERE "IdBodega" IS NULL;
    ALTER TABLE "Citas" ALTER COLUMN "IdBodega" SET NOT NULL;
    CREATE INDEX IF NOT EXISTS "IdxCitasIdBodega" ON "Citas"("IdBodega");
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'FranjasPermitidasCita' AND column_name = 'IdBodega'
  ) THEN
    ALTER TABLE "FranjasPermitidasCita" ADD COLUMN "IdBodega" INTEGER REFERENCES "Bodegas"("Id");
    UPDATE "FranjasPermitidasCita" SET "IdBodega" = (SELECT MIN("Id") FROM "Bodegas") WHERE "IdBodega" IS NULL;
    ALTER TABLE "FranjasPermitidasCita" ALTER COLUMN "IdBodega" SET NOT NULL;
    CREATE INDEX IF NOT EXISTS "IdxFranjasPermitidasCitaBodega" ON "FranjasPermitidasCita"("IdBodega");
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'FranjasPermitidasCitaFecha' AND column_name = 'IdBodega'
  ) THEN
    ALTER TABLE "FranjasPermitidasCitaFecha" ADD COLUMN "IdBodega" INTEGER REFERENCES "Bodegas"("Id");
    UPDATE "FranjasPermitidasCitaFecha" SET "IdBodega" = (SELECT MIN("Id") FROM "Bodegas") WHERE "IdBodega" IS NULL;
    ALTER TABLE "FranjasPermitidasCitaFecha" ALTER COLUMN "IdBodega" SET NOT NULL;
    CREATE INDEX IF NOT EXISTS "IdxFranjasPermitidasCitaFechaBodega" ON "FranjasPermitidasCitaFecha"("IdBodega");
  END IF;
END $$;

ALTER TABLE "FranjasPermitidasCitaFecha" DROP CONSTRAINT IF EXISTS "UqFranjaFechaOrden";
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    INNER JOIN pg_class t ON c.conrelid = t.oid
    INNER JOIN pg_namespace n ON t.relnamespace = n.oid
    WHERE n.nspname = 'public'
      AND t.relname = 'FranjasPermitidasCitaFecha'
      AND c.conname = 'UqFranjaFechaBodegaOrden'
  ) THEN
    ALTER TABLE "FranjasPermitidasCitaFecha"
      ADD CONSTRAINT "UqFranjaFechaBodegaOrden" UNIQUE ("Fecha", "IdBodega", "Orden");
  END IF;
END $$;

COMMENT ON TABLE "FranjasPermitidasCita" IS 'Turnos semanales por bodega: cada fila es un cupo agendable (HoraInicio–HoraFin, duración implícita).';
COMMENT ON TABLE "FranjasPermitidasCitaFecha" IS 'Turnos por fecha y bodega; si existen para un día+bodega, reemplazan la regla semanal de esa bodega.';
