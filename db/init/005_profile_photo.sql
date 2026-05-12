CREATE TABLE IF NOT EXISTS "PerfilFoto" (
  "Id" SERIAL PRIMARY KEY,
  "IdCredencial" INTEGER UNIQUE NOT NULL REFERENCES "Credenciales"("IdCredencial"),
  "FotoUrl" VARCHAR(500) NULL,
  "ActualizadoEn" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "IdxPerfilFotoIdCredencial" ON "PerfilFoto"("IdCredencial");
