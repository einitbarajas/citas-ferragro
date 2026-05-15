"""
Libera un correo bloqueado por credenciales huérfanas (sin usuario ni proveedor).

Uso (desde backend/):
  set DATABASE_URL=postgresql://...
  python scripts/release_orphan_email.py ebarajas@ferragro.com
"""
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.credential_cleanup import release_email_for_reuse


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/release_orphan_email.py <correo>", file=sys.stderr)
        return 1
    email = sys.argv[1].strip()
    if not email:
        print("Correo vacío.", file=sys.stderr)
        return 1

    if not settings.database_url:
        print("DATABASE_URL no configurada.", file=sys.stderr)
        return 1

    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        try:
            removed = release_email_for_reuse(db, email)
            db.commit()
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
    if removed:
        print(f"Eliminadas credenciales huérfanas: {removed}")
    else:
        print("No había credenciales huérfanas (revisa mayúsculas o cuenta activa).")
    print("Listo. Ya puedes crear el usuario con ese correo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
