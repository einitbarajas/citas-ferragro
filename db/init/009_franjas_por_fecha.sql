CREATE TABLE IF NOT EXISTS "FranjasPermitidasCitaFecha" (
  "Id" SERIAL PRIMARY KEY,
  "Fecha" DATE NOT NULL,
  "HoraInicio" TIME NOT NULL,
  "HoraFin" TIME NOT NULL,
  "Orden" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "ChkFranjaFechaPermitida" CHECK ("HoraFin" > "HoraInicio"),
  CONSTRAINT "UqFranjaFechaOrden" UNIQUE ("Fecha", "Orden")
);

CREATE INDEX IF NOT EXISTS "IdxFranjasPermitidasCitaFechaFecha" ON "FranjasPermitidasCitaFecha"("Fecha");

COMMENT ON TABLE "FranjasPermitidasCitaFecha" IS 'Franjas especiales por fecha exacta. Si existen para un día, reemplazan la regla semanal.';
