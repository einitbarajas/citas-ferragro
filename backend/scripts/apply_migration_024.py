"""Aplica db/init/024_audit_actor_role.sql (columna RolActor en HistorialCambios)."""
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal

_REPO_ROOT = Path(__file__).resolve().parents[2]
SQL = (_REPO_ROOT / "db" / "init" / "024_audit_actor_role.sql").read_text(
    encoding="utf-8"
)


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Migración 024 aplicada correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
