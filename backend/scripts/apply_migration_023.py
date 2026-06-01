"""Aplica db/init/023_notificacion_lecturas.sql."""
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal

SQL = (Path(__file__).resolve().parents[1] / "db" / "init" / "023_notificacion_lecturas.sql").read_text(
    encoding="utf-8"
)


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Migración 023 aplicada correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
