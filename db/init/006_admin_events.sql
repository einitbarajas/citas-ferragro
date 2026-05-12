CREATE TABLE IF NOT EXISTS "AuditoriaSistema" (
  "Id" SERIAL PRIMARY KEY,
  "IdActor" VARCHAR(30) NOT NULL,
  "Accion" VARCHAR(80) NOT NULL,
  "Descripcion" TEXT NOT NULL,
  "CreadoEn" TIMESTAMPTZ NOT NULL,
  "DocumentoObjetivo" VARCHAR(30) NULL
);

CREATE INDEX IF NOT EXISTS "IdxAuditoriaSistemaIdActor" ON "AuditoriaSistema"("IdActor");
CREATE INDEX IF NOT EXISTS "IdxAuditoriaSistemaDocumentoObjetivo" ON "AuditoriaSistema"("DocumentoObjetivo");
