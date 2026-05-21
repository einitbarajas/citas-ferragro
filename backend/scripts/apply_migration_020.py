"""Aplica db/init/020_admin_bodega.sql (rol AdminBodega + UsuariosBodegas)."""
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal

SQL = (Path(__file__).resolve().parents[2] / "db" / "init" / "020_admin_bodega.sql").read_text(encoding="utf-8")


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Migración 020 aplicada correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
