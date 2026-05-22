"""Aplica db/init/021_equipos_descarga_integridad.sql (citas/franjas + trigger por bodega)."""
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal

SQL = (Path(__file__).resolve().parents[2] / "db" / "init" / "021_equipos_descarga_integridad.sql").read_text(
    encoding="utf-8"
)


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("Migración 021 aplicada correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
