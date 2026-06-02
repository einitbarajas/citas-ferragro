-- Migration 024: agrega columna RolActor a HistorialCambios
ALTER TABLE "HistorialCambios"
    ADD COLUMN IF NOT EXISTS "RolActor" VARCHAR(30) NULL;

COMMENT ON COLUMN "HistorialCambios"."RolActor" IS
    'Rol del usuario que ejecutó la acción (Admin, AdminBodega, Logistica, Proveedor, Sistema)';
