#!/usr/bin/env python3
"""Crea o actualiza el usuario AdminBodega en producción y asigna bodegas activas."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.user_warehouse import UserWarehouse
from app.models.warehouse import Warehouse

ADMIN_BODEGA_DOC = os.getenv("ADMIN_BODEGA_DOCUMENT", "90000002")
ADMIN_BODEGA_EMAIL = os.getenv("ADMIN_BODEGA_EMAIL", "admin.bodega@ferragro.com").strip().lower()
ADMIN_BODEGA_NAME = os.getenv("ADMIN_BODEGA_NAME", "Administrador de Bodega")
ADMIN_BODEGA_PASSWORD = os.getenv("ADMIN_BODEGA_PASSWORD", "FerragroPortal2026!")


def main() -> int:
    if "render.com" not in (settings.database_url or ""):
        print("ADVERTENCIA: DATABASE_URL no parece Render.", file=sys.stderr)

    with SessionLocal() as db:
        role = db.execute(select(Role).where(Role.name == UserRole.admin_bodega)).scalar_one_or_none()
        if not role:
            print("ERROR: falta rol AdminBodega. Ejecuta db/arreglar-esquema-produccion.ps1", file=sys.stderr)
            return 1

        from app.models.credential import Credential

        cred = db.execute(
            select(Credential).where(Credential.email.ilike(ADMIN_BODEGA_EMAIL))
        ).scalar_one_or_none()
        if cred is None:
            cred = Credential(email=ADMIN_BODEGA_EMAIL, password_hash=get_password_hash(ADMIN_BODEGA_PASSWORD))
            db.add(cred)
            db.flush()
        elif not verify_password(ADMIN_BODEGA_PASSWORD, cred.password_hash):
            cred.password_hash = get_password_hash(ADMIN_BODEGA_PASSWORD)

        user = db.get(User, ADMIN_BODEGA_DOC)
        if user is None:
            user = User(
                document_id=ADMIN_BODEGA_DOC,
                full_name=ADMIN_BODEGA_NAME,
                credential_id=cred.id,
                role_id=role.id,
            )
            db.add(user)
        else:
            user.full_name = ADMIN_BODEGA_NAME
            user.credential_id = cred.id
            user.role_id = role.id

        db.flush()
        warehouses = db.execute(select(Warehouse).where(Warehouse.active.is_(True))).scalars().all()
        existing = set(
            db.execute(
                select(UserWarehouse.warehouse_id).where(
                    UserWarehouse.document_id == ADMIN_BODEGA_DOC
                )
            ).scalars().all()
        )
        for wh in warehouses:
            if wh.id not in existing:
                db.add(UserWarehouse(document_id=ADMIN_BODEGA_DOC, warehouse_id=wh.id))

        db.commit()

    print("Administrador de bodega listo:")
    print(f"  Documento:  {ADMIN_BODEGA_DOC}")
    print(f"  Correo:     {ADMIN_BODEGA_EMAIL}")
    print(f"  Contraseña: {ADMIN_BODEGA_PASSWORD}")
    print(f"  Bodegas:    todas las activas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
