DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'Proveedores'
      AND column_name = 'IdNit'
      AND numeric_precision = 9
  ) THEN
    ALTER TABLE "Proveedores"
      ALTER COLUMN "IdNit" TYPE NUMERIC(10,0) USING "IdNit"::NUMERIC(10,0);
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'Citas'
      AND column_name = 'IdProveedor'
      AND numeric_precision = 9
  ) THEN
    ALTER TABLE "Citas"
      ALTER COLUMN "IdProveedor" TYPE NUMERIC(10,0) USING "IdProveedor"::NUMERIC(10,0);
  END IF;
END $$;
