"""Apply 024 weekly franja ISO weekday column (idempotent)."""
from sqlalchemy import text

from app.db.session import SessionLocal

STATEMENTS = [
    'ALTER TABLE "FranjasPermitidasCita" ADD COLUMN IF NOT EXISTS "DiaSemanaIso" SMALLINT',
    'UPDATE "FranjasPermitidasCita" SET "DiaSemanaIso" = 1 WHERE "DiaSemanaIso" IS NULL',
    'DROP INDEX IF EXISTS "UqFranjaBodegaOrdenCompartido"',
    'DROP INDEX IF EXISTS "UqFranjaBodegaEquipoOrden"',
    """INSERT INTO "FranjasPermitidasCita" (
  "IdBodega", "IdEquipoDescargaBodega", "HoraInicio", "HoraFin", "Orden", "DiaSemanaIso"
)
SELECT f."IdBodega", f."IdEquipoDescargaBodega", f."HoraInicio", f."HoraFin", f."Orden", d."DiaSemanaIso"
FROM "FranjasPermitidasCita" f
CROSS JOIN (VALUES (2), (3), (4), (5)) AS d("DiaSemanaIso")
WHERE f."DiaSemanaIso" = 1
  AND NOT EXISTS (
    SELECT 1 FROM "FranjasPermitidasCita" x
    WHERE x."IdBodega" = f."IdBodega" AND x."Orden" = f."Orden"
      AND x."HoraInicio" = f."HoraInicio" AND x."HoraFin" = f."HoraFin"
      AND x."DiaSemanaIso" = d."DiaSemanaIso"
      AND ((x."IdEquipoDescargaBodega" IS NULL AND f."IdEquipoDescargaBodega" IS NULL)
        OR x."IdEquipoDescargaBodega" = f."IdEquipoDescargaBodega")
  )""",
    'ALTER TABLE "FranjasPermitidasCita" ALTER COLUMN "DiaSemanaIso" SET NOT NULL',
    'ALTER TABLE "FranjasPermitidasCita" DROP CONSTRAINT IF EXISTS "ChkFranjaDiaSemanaIso"',
    'ALTER TABLE "FranjasPermitidasCita" ADD CONSTRAINT "ChkFranjaDiaSemanaIso" CHECK ("DiaSemanaIso" BETWEEN 1 AND 7)',
    """CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaBodegaOrdenCompartido"
  ON "FranjasPermitidasCita" ("IdBodega", "DiaSemanaIso", "Orden")
  WHERE "IdEquipoDescargaBodega" IS NULL""",
    """CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaBodegaEquipoDiaOrden"
  ON "FranjasPermitidasCita" ("IdBodega", "IdEquipoDescargaBodega", "DiaSemanaIso", "Orden")
  WHERE "IdEquipoDescargaBodega" IS NOT NULL""",
]


def main() -> None:
    db = SessionLocal()
    try:
        for stmt in STATEMENTS:
            db.execute(text(stmt))
        db.commit()
        print("024 applied")
    finally:
        db.close()


if __name__ == "__main__":
    main()
