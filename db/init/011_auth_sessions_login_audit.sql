-- Sesiones de refresh token persistidas (invalidación por dispositivo / todas).
CREATE TABLE IF NOT EXISTS "SesionesRefresh" (
  "Id" SERIAL PRIMARY KEY,
  "IdCredencial" INTEGER NOT NULL REFERENCES "Credenciales"("IdCredencial") ON DELETE CASCADE,
  "Jti" UUID NOT NULL UNIQUE,
  "CreadoEn" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  "ExpiraEn" TIMESTAMPTZ NOT NULL,
  "RevocadoEn" TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS "IdxSesionesRefreshIdCredencial" ON "SesionesRefresh"("IdCredencial");
CREATE INDEX IF NOT EXISTS "IdxSesionesRefreshExpira" ON "SesionesRefresh"("ExpiraEn");

-- Control de intentos de login y bloqueo temporal.
CREATE TABLE IF NOT EXISTS "IntentosLogin" (
  "IdCredencial" INTEGER PRIMARY KEY REFERENCES "Credenciales"("IdCredencial") ON DELETE CASCADE,
  "FallosConsecutivos" INTEGER NOT NULL DEFAULT 0,
  "BloqueadoHasta" TIMESTAMPTZ
);

-- Auditoría de eventos de login (éxito / fallo).
CREATE TABLE IF NOT EXISTS "AuditoriaLogin" (
  "Id" SERIAL PRIMARY KEY,
  "IdCredencial" INTEGER REFERENCES "Credenciales"("IdCredencial") ON DELETE SET NULL,
  "Correo" VARCHAR(255) NOT NULL,
  "Exito" BOOLEAN NOT NULL,
  "DireccionIp" VARCHAR(45),
  "UserAgent" TEXT,
  "MotivoFallo" VARCHAR(255),
  "CreadoEn" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "IdxAuditoriaLoginCreado" ON "AuditoriaLogin"("CreadoEn");
CREATE INDEX IF NOT EXISTS "IdxAuditoriaLoginCorreo" ON "AuditoriaLogin"("Correo");

-- Ejecuciones de recordatorios automatizados (trazabilidad scheduler).
CREATE TABLE IF NOT EXISTS "EjecucionesRecordatorio" (
  "Id" SERIAL PRIMARY KEY,
  "IdCita" INTEGER NOT NULL REFERENCES "Citas"("Id") ON DELETE CASCADE,
  "Tipo" VARCHAR(40) NOT NULL DEFAULT 'recordatorio_proximo',
  "Estado" VARCHAR(30) NOT NULL,
  "Detalle" TEXT,
  "EjecutadoEn" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "IdxEjecRecordatorioCita" ON "EjecucionesRecordatorio"("IdCita");

-- Trazabilidad detallada en historial (valor anterior / nuevo por campo crítico).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'HistorialCambios' AND column_name = 'CampoCritico'
  ) THEN
    ALTER TABLE "HistorialCambios" ADD COLUMN "CampoCritico" VARCHAR(80);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'HistorialCambios' AND column_name = 'ValorAnterior'
  ) THEN
    ALTER TABLE "HistorialCambios" ADD COLUMN "ValorAnterior" TEXT;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'HistorialCambios' AND column_name = 'ValorNuevo'
  ) THEN
    ALTER TABLE "HistorialCambios" ADD COLUMN "ValorNuevo" TEXT;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS "IdxCitasEstado" ON "Citas"("Estado");
