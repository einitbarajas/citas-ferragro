CREATE TABLE IF NOT EXISTS "NotificacionLecturas" (
    "Id" SERIAL PRIMARY KEY,
    "IdNotificacion" INTEGER NOT NULL REFERENCES "Notificaciones" ("Id") ON DELETE CASCADE,
    "IdLector" VARCHAR(30) NOT NULL,
    "LeidaEn" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT "UQ_NotificacionLecturas" UNIQUE ("IdNotificacion", "IdLector")
);

CREATE INDEX IF NOT EXISTS "ix_notificacion_lecturas_lector"
    ON "NotificacionLecturas" ("IdLector");
