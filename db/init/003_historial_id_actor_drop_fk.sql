-- Parche para bases ya creadas con 001_schema anterior:
-- quita la FK de "HistorialCambios"."IdActor" hacia "Usuarios" para permitir actores proveedor (IdNit como texto)
-- sin borrar filas de ninguna tabla.

ALTER TABLE "HistorialCambios" DROP CONSTRAINT IF EXISTS "HistorialCambios_IdActor_fkey";

COMMENT ON COLUMN "HistorialCambios"."IdActor" IS 'Identificador del actor: IdDocumento (Usuarios) o IdProveedor en texto.';

CREATE INDEX IF NOT EXISTS "IdxHistorialCambiosIdActor" ON "HistorialCambios"("IdActor");
