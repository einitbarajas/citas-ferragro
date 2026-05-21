-- Equipos de descarga por bodega (muelles), franjas y citas por equipo.
-- Idempotente.

CREATE TABLE IF NOT EXISTS "EquiposDescargaBodega" (
  "Id" SERIAL PRIMARY KEY,
  "IdBodega" INTEGER NOT NULL REFERENCES "Bodegas"("Id") ON DELETE CASCADE,
  "Nombre" VARCHAR(80) NOT NULL,
  "Activo" BOOLEAN NOT NULL DEFAULT TRUE,
  "Orden" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "UqEquipoDescargaBodegaNombre" UNIQUE ("IdBodega", "Nombre")
);

CREATE INDEX IF NOT EXISTS "IdxEquiposDescargaBodegaIdBodega" ON "EquiposDescargaBodega"("IdBodega");

COMMENT ON TABLE "EquiposDescargaBodega" IS 'Muelles/equipos de descarga en una bodega; cada uno tiene cupo y franjas propias.';

-- Sincronizar filas desde el contador legacy en Bodegas (si existe).
INSERT INTO "EquiposDescargaBodega" ("IdBodega", "Nombre", "Activo", "Orden")
SELECT b."Id", 'Equipo ' || gs.n::TEXT, TRUE, gs.n - 1
FROM "Bodegas" b
CROSS JOIN LATERAL generate_series(1, GREATEST(COALESCE(b."EquiposDescarga", 1), 1)) AS gs(n)
WHERE NOT EXISTS (
  SELECT 1 FROM "EquiposDescargaBodega" e WHERE e."IdBodega" = b."Id"
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Citas' AND column_name = 'IdEquipoDescargaBodega'
  ) THEN
    ALTER TABLE "Citas" ADD COLUMN "IdEquipoDescargaBodega" INTEGER REFERENCES "EquiposDescargaBodega"("Id");
    UPDATE "Citas" c
    SET "IdEquipoDescargaBodega" = (
      SELECT e."Id" FROM "EquiposDescargaBodega" e
      WHERE e."IdBodega" = c."IdBodega" AND e."Activo" = TRUE
      ORDER BY e."Orden", e."Id"
      LIMIT 1
    );
    ALTER TABLE "Citas" ALTER COLUMN "IdEquipoDescargaBodega" SET NOT NULL;
    CREATE INDEX IF NOT EXISTS "IdxCitasIdEquipoDescargaBodega" ON "Citas"("IdEquipoDescargaBodega");
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Citas' AND column_name = 'IndiceEquipoProveedor'
  ) THEN
    ALTER TABLE "Citas" ADD COLUMN "IndiceEquipoProveedor" INTEGER NOT NULL DEFAULT 1
      CONSTRAINT "ChkCitasIndiceEquipoProveedor" CHECK ("IndiceEquipoProveedor" >= 1 AND "IndiceEquipoProveedor" <= 20);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'FranjasPermitidasCita' AND column_name = 'IdEquipoDescargaBodega'
  ) THEN
    ALTER TABLE "FranjasPermitidasCita"
      ADD COLUMN "IdEquipoDescargaBodega" INTEGER REFERENCES "EquiposDescargaBodega"("Id") ON DELETE CASCADE;
    CREATE INDEX IF NOT EXISTS "IdxFranjasPermitidasCitaEquipo" ON "FranjasPermitidasCita"("IdEquipoDescargaBodega");
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'FranjasPermitidasCitaFecha' AND column_name = 'IdEquipoDescargaBodega'
  ) THEN
    ALTER TABLE "FranjasPermitidasCitaFecha"
      ADD COLUMN "IdEquipoDescargaBodega" INTEGER REFERENCES "EquiposDescargaBodega"("Id") ON DELETE CASCADE;
    CREATE INDEX IF NOT EXISTS "IdxFranjasPermitidasCitaFechaEquipo" ON "FranjasPermitidasCitaFecha"("IdEquipoDescargaBodega");
  END IF;
END $$;
