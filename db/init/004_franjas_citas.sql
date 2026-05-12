-- Franjas locales del día en las que se permite INICIAR una cita (zona en app.settings.business_timezone).
-- Idempotente: crea tabla y datos por defecto solo si la tabla está vacía.

CREATE TABLE IF NOT EXISTS "FranjasPermitidasCita" (
  "Id" SERIAL PRIMARY KEY,
  "HoraInicio" TIME NOT NULL,
  "HoraFin" TIME NOT NULL,
  "Orden" INTEGER NOT NULL DEFAULT 0,
  CONSTRAINT "ChkFranjaPermitida" CHECK ("HoraFin" > "HoraInicio")
);

COMMENT ON TABLE "FranjasPermitidasCita" IS 'Ventanas horarias permitidas para el inicio de citas (solo Admin las edita desde el dashboard).';

INSERT INTO "FranjasPermitidasCita" ("HoraInicio", "HoraFin", "Orden")
SELECT v.hi, v.hf, v.ord
FROM (
  VALUES
    ('08:00'::time, '11:00'::time, 1),
    ('13:00'::time, '16:00'::time, 2)
) AS v(hi, hf, ord)
WHERE NOT EXISTS (SELECT 1 FROM "FranjasPermitidasCita" LIMIT 1);
