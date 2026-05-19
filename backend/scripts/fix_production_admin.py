#!/usr/bin/env python3
"""Corrige Admin en producción sin esperar deploy. Requiere DATABASE_URL de Render."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.admin_bootstrap import ensure_production_admin
from app.services.credential_cleanup import purge_orphan_credentials


def main() -> int:
    on_render = "render.com" in (settings.database_url or "")
    if not on_render and settings.environment.lower() != "production":
        print("ADVERTENCIA: DATABASE_URL no parece ser Render/producción.", file=sys.stderr)
        answer = input("¿Continuar? (si/no): ").strip().lower()
        if answer not in ("si", "s", "yes", "y"):
            return 1

    object.__setattr__(settings, "environment", "production")
    object.__setattr__(settings, "admin_bootstrap_enabled", True)

    with SessionLocal() as db:
        purge_orphan_credentials(db)
        ensure_production_admin(db)
        db.commit()

    print("Listo. Inicia sesión con:")
    print(f"  Correo:     {settings.admin_bootstrap_email}")
    print(f"  Contraseña: {settings.admin_bootstrap_password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
