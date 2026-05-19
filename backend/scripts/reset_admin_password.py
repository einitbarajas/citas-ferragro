"""
Restablece la contraseña del usuario Admin (documento 90000001).

Uso (desde backend/, con External Database URL de Render):
  set DATABASE_URL=postgresql://...
  python scripts/reset_admin_password.py
  python scripts/reset_admin_password.py --password "OtraClave12!"
"""
import argparse
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash


def main() -> int:
    parser = argparse.ArgumentParser(description="Restablece contraseña del Admin en BD.")
    parser.add_argument("--document-id", default="90000001")
    parser.add_argument("--password", default="FerragroAdmin2026!")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.", file=sys.stderr)
        return 1
    if not settings.database_url:
        print("DATABASE_URL no configurada.", file=sys.stderr)
        return 1

    pwd_hash = get_password_hash(args.password)
    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        row = db.execute(
            text(
                'SELECT "IdCredencial" AS cid FROM "Usuarios" WHERE "IdDocumento" = :doc LIMIT 1'
            ),
            {"doc": args.document_id},
        ).mappings().first()
        if not row:
            print(f"No existe usuario con documento {args.document_id}.", file=sys.stderr)
            return 2
        cid = int(row["cid"])
        db.execute(
            text('UPDATE "Credenciales" SET "HashContrasena" = :h WHERE "IdCredencial" = :cid'),
            {"h": pwd_hash, "cid": cid},
        )
        db.execute(text('DELETE FROM "EstadoResetContrasena" WHERE "IdCredencial" = :cid'), {"cid": cid})
        db.commit()
    print(f"Contraseña actualizada para documento {args.document_id}.")
    print(f"Inicia sesión con la clave que definiste (por defecto: {args.password}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
