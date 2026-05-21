-- Rol administrador de bodega (alcance por bodegas asignadas en UsuariosBodegas).
INSERT INTO "Rol" ("Nombre")
VALUES ('AdminBodega')
ON CONFLICT ("Nombre") DO NOTHING;

CREATE TABLE IF NOT EXISTS "UsuariosBodegas" (
  "IdDocumento" VARCHAR(30) NOT NULL REFERENCES "Usuarios"("IdDocumento") ON DELETE CASCADE,
  "IdBodega" INTEGER NOT NULL REFERENCES "Bodegas"("Id") ON DELETE CASCADE,
  PRIMARY KEY ("IdDocumento", "IdBodega")
);

CREATE INDEX IF NOT EXISTS "IdxUsuariosBodegasBodega"
  ON "UsuariosBodegas" ("IdBodega");
