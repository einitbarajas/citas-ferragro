"""
Elimina credenciales sin usuario ni proveedor (huérfanas).

Uso en Render (build o manual, desde backend/):
  python scripts/purge_orphan_credentials.py
"""
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.admin_bootstrap import ensure_production_admin
from app.services.credential_cleanup import purge_orphan_credentials


def main() -> int:
    if not settings.database_url:
        print("DATABASE_URL no configurada; omitiendo limpieza.", file=sys.stderr)
        return 0

    is_render = "render.com" in settings.database_url
    if is_render:
        object.__setattr__(settings, "environment", "production")
        object.__setattr__(settings, "admin_bootstrap_enabled", True)

    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        removed = purge_orphan_credentials(db)
        if is_render:
            ensure_production_admin(db)
            print("Admin de producción verificado (ebarajas@ferragro.com).")
        db.commit()
    if removed:
        print(f"Credenciales huérfanas eliminadas: {removed}")
    else:
        print("No había credenciales huérfanas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
