from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import engine


def main() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                'ALTER TABLE "Notificaciones" '
                'ALTER COLUMN "IdProveedorDestinatario" TYPE NUMERIC(10,0) '
                'USING "IdProveedorDestinatario"::numeric'
            )
        )
    print("Notificaciones.IdProveedorDestinatario migrated to NUMERIC(10,0)")


if __name__ == "__main__":
    main()
