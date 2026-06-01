"""Aplica db/init/022_notificaciones_actor_auditoria.sql."""
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal

SQL = (
    Path(__file__).resolve().parents[1] / "db" / "init" / "022_notificaciones_actor_auditoria.sql"
).read_text(encoding="utf-8")


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Migración 022 aplicada correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
