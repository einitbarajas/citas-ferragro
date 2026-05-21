from sqlalchemy import text

from app.db.session import SessionLocal

def main() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT conname, pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'FranjasPermitidasCitaFecha' AND c.contype = 'u'
                """
            )
        ).fetchall()
        print("unique constraints:", rows)
        idx = db.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'FranjasPermitidasCitaFecha'
                  AND indexname LIKE 'UqFranja%'
                """
            )
        ).fetchall()
        print("indexes:")
        for i in idx:
            print(" ", i)
    finally:
        db.close()


if __name__ == "__main__":
    main()
