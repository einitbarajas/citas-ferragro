-- Notificaciones: actor, bodega, proveedor de cita; cita opcional al eliminar.
-- Historial: IP del actor.

ALTER TABLE "Notificaciones" DROP CONSTRAINT IF EXISTS "Notificaciones_IdCita_fkey";

ALTER TABLE "Notificaciones"
    ALTER COLUMN "IdCita" DROP NOT NULL;

ALTER TABLE "Notificaciones"
    ADD CONSTRAINT "Notificaciones_IdCita_fkey"
    FOREIGN KEY ("IdCita") REFERENCES "Citas" ("Id") ON DELETE SET NULL;

ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "IdBodega" INTEGER;
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "IdProveedorCita" NUMERIC(10, 0);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "IdActor" VARCHAR(30);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "RolActor" VARCHAR(30);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "EtiquetaActor" VARCHAR(200);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "Accion" VARCHAR(40);
ALTER TABLE "Notificaciones" ADD COLUMN IF NOT EXISTS "EstadoCita" VARCHAR(30);

CREATE INDEX IF NOT EXISTS "ix_notificaciones_bodega" ON "Notificaciones" ("IdBodega");
CREATE INDEX IF NOT EXISTS "ix_notificaciones_proveedor_cita" ON "Notificaciones" ("IdProveedorCita");

UPDATE "Notificaciones" n
SET
    "IdBodega" = c."IdBodega",
    "IdProveedorCita" = c."IdProveedor"
FROM "Citas" c
WHERE n."IdCita" = c."Id"
  AND (n."IdBodega" IS NULL OR n."IdProveedorCita" IS NULL);

ALTER TABLE "HistorialCambios" ADD COLUMN IF NOT EXISTS "IpOrigen" VARCHAR(45);
