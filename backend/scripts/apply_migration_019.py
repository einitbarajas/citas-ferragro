"""Apply 019 weekly franja unique indexes (idempotent)."""
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal

SQL = (Path(__file__).resolve().parents[2] / "db" / "init" / "019_franjas_semanales_unique_por_equipo.sql").read_text(
    encoding="utf-8"
)


def main() -> None:
    db = SessionLocal()
    try:
        for stmt in (s.strip() for s in SQL.split(";") if s.strip() and not s.strip().startswith("--")):
            db.execute(text(stmt))
        db.commit()
        print("019 applied")
    finally:
        db.close()


if __name__ == "__main__":
    main()
