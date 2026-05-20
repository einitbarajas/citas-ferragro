-- Estado de cuenta proveedor: activo | suspendido (purga programada tras 6 meses en API).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'Estado'
  ) THEN
    ALTER TABLE "Proveedores" ADD COLUMN "Estado" VARCHAR(20) NOT NULL DEFAULT 'activo';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'SuspendidoEn'
  ) THEN
    ALTER TABLE "Proveedores" ADD COLUMN "SuspendidoEn" TIMESTAMPTZ;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'MotivoSuspension'
  ) THEN
    ALTER TABLE "Proveedores" ADD COLUMN "MotivoSuspension" TEXT;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'SuspendidoPor'
  ) THEN
    ALTER TABLE "Proveedores" ADD COLUMN "SuspendidoPor" VARCHAR(30);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'Proveedores' AND column_name = 'PurgaProgramadaEn'
  ) THEN
    ALTER TABLE "Proveedores" ADD COLUMN "PurgaProgramadaEn" TIMESTAMPTZ;
  END IF;
END $$;

UPDATE "Proveedores" SET "Estado" = 'activo' WHERE "Estado" IS NULL OR TRIM("Estado") = '';

DO $$
BEGIN
  ALTER TABLE "Proveedores" ADD CONSTRAINT "ChkProveedoresEstado"
    CHECK ("Estado" IN ('activo', 'suspendido'));
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON COLUMN "Proveedores"."Estado" IS 'activo: acceso normal; suspendido: sin login, purga programada.';
COMMENT ON COLUMN "Proveedores"."PurgaProgramadaEn" IS 'Fecha UTC en la que el job eliminará datos salvo AuditoriaSistema.';
