"""Lista usuarios internos y bodegas asignadas (diagnóstico)."""
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.credential import Credential
from app.models.role import Role
from app.models.user import User
from app.models.user_warehouse import UserWarehouse
from app.models.warehouse import Warehouse


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(
                User.document_id,
                User.full_name,
                Role.name,
                Credential.email,
            )
            .join(Role, User.role_id == Role.id)
            .join(Credential, User.credential_id == Credential.id)
            .where(Role.name.in_(["Admin", "Logistica", "AdminBodega"]))
            .order_by(Role.name, User.full_name)
        ).all()
        print("=== USUARIOS INTERNOS ===")
        for doc, name, role, email in rows:
            wh = db.execute(
                select(Warehouse.id, Warehouse.name)
                .join(UserWarehouse, UserWarehouse.warehouse_id == Warehouse.id)
                .where(UserWarehouse.document_id == doc)
                .order_by(Warehouse.id)
            ).all()
            wh_txt = ", ".join(f"{wid} ({wname})" for wid, wname in wh) if wh else "(ninguna)"
            need = role in ("Logistica", "AdminBodega")
            ok = "OK" if not need or wh else "FALTA bodega"
            print(f"- {name} | {role} | doc {doc} | {email}")
            print(f"  Bodegas: {wh_txt} | Requiere bodega: {'SI' if need else 'no'} | {ok}")

        print()
        orphans = db.execute(
            text(
                """
                SELECT u."IdDocumento", r."Nombre"
                FROM "Usuarios" u
                JOIN "Rol" r ON u."IdRol" = r."Id"
                WHERE r."Nombre" IN ('Logistica', 'AdminBodega')
                AND NOT EXISTS (
                    SELECT 1 FROM "UsuariosBodegas" ub
                    WHERE ub."IdDocumento" = u."IdDocumento"
                )
                """
            )
        ).all()
        if orphans:
            print("=== SIN BODEGAS (no reciben avisos por bodega) ===")
            for doc, role in orphans:
                print(f"  {doc} ({role})")
        else:
            print("=== Todos Logistica/AdminBodega tienen al menos una bodega ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
