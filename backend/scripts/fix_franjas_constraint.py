"""One-off: drop legacy UqFranjaFechaBodegaOrden and ensure partial unique indexes."""
from sqlalchemy import text

from app.db.session import SessionLocal

def main() -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                'ALTER TABLE "FranjasPermitidasCitaFecha" '
                'DROP CONSTRAINT IF EXISTS "UqFranjaFechaBodegaOrden"'
            )
        )
        db.execute(text('DROP INDEX IF EXISTS "UqFranjaFechaBodegaOrden"'))
        db.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaFechaBodegaOrdenCompartido"
                  ON "FranjasPermitidasCitaFecha" ("Fecha", "IdBodega", "Orden")
                  WHERE "IdEquipoDescargaBodega" IS NULL
                """
            )
        )
        db.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS "UqFranjaFechaBodegaEquipoOrden"
                  ON "FranjasPermitidasCitaFecha" ("Fecha", "IdBodega", "IdEquipoDescargaBodega", "Orden")
                  WHERE "IdEquipoDescargaBodega" IS NOT NULL
                """
            )
        )
        db.commit()
        print("fixed constraints")
    finally:
        db.close()


if __name__ == "__main__":
    main()
