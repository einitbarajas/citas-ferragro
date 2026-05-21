-- Equipos de descarga en paralelo: bodega (muelles) y proveedor (camiones/equipos propios).
-- Idempotente.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Bodegas' AND column_name = 'EquiposDescarga'
  ) THEN
    ALTER TABLE "Bodegas"
      ADD COLUMN "EquiposDescarga" INTEGER NOT NULL DEFAULT 1
      CONSTRAINT "ChkBodegasEquiposDescarga" CHECK ("EquiposDescarga" >= 1 AND "EquiposDescarga" <= 20);
    COMMENT ON COLUMN "Bodegas"."EquiposDescarga" IS
      'Cantidad de equipos o muelles de descarga en paralelo en esta bodega.';
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'EquiposDescarga'
  ) THEN
    ALTER TABLE "Proveedores"
      ADD COLUMN "EquiposDescarga" INTEGER NOT NULL DEFAULT 1
      CONSTRAINT "ChkProveedoresEquiposDescarga" CHECK ("EquiposDescarga" >= 1 AND "EquiposDescarga" <= 20);
    COMMENT ON COLUMN "Proveedores"."EquiposDescarga" IS
      'Equipos de descarga del proveedor; permite varias citas simultáneas (misma hora) hasta este límite.';
  END IF;
END $$;
