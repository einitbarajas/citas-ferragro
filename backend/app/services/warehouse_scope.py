"""Alcance por bodega para roles AdminBodega y Logística."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import SecurityPrincipal
from app.models.user import UserRole
from app.models.user_warehouse import UserWarehouse
from app.models.warehouse import Warehouse

ROLE_ADMIN_BODEGA = UserRole.admin_bodega
ROLE_LOGISTICA = UserRole.logistica
GLOBAL_ADMIN_ROLE = UserRole.admin
INTERNAL_STAFF_ROLES = frozenset({UserRole.admin, ROLE_LOGISTICA, ROLE_ADMIN_BODEGA})
WAREHOUSE_ADMIN_ROLES = frozenset({UserRole.admin, ROLE_ADMIN_BODEGA})
WAREHOUSE_SCOPED_ROLES = frozenset({ROLE_ADMIN_BODEGA, ROLE_LOGISTICA})


def role_requires_warehouse_assignments(role_name: str) -> bool:
    return role_name in WAREHOUSE_SCOPED_ROLES


def list_user_warehouse_ids(db: Session, document_id: str) -> list[int]:
    rows = db.execute(
        select(UserWarehouse.warehouse_id)
        .where(UserWarehouse.document_id == document_id)
        .order_by(UserWarehouse.warehouse_id.asc())
    ).scalars().all()
    return [int(x) for x in rows]


def sync_user_warehouse_assignments(db: Session, document_id: str, warehouse_ids: list[int]) -> None:
    unique_ids = sorted({int(w) for w in warehouse_ids if int(w) > 0})
    db.execute(delete(UserWarehouse).where(UserWarehouse.document_id == document_id))
    for wid in unique_ids:
        db.add(UserWarehouse(document_id=document_id, warehouse_id=wid))


def validate_warehouse_ids_exist(db: Session, warehouse_ids: list[int]) -> None:
    if not warehouse_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes asignar al menos una bodega a este usuario.",
        )
    found = db.execute(
        select(Warehouse.id).where(Warehouse.id.in_(warehouse_ids))
    ).scalars().all()
    if len(found) != len(set(warehouse_ids)):
        raise HTTPException(status_code=400, detail="Una o más bodegas asignadas no existen.")


def resolve_allowed_warehouse_ids(db: Session, principal: SecurityPrincipal) -> list[int] | None:
    """
    None = acceso a todas las bodegas (Admin global).
    Lista (posiblemente vacía) = solo esas bodegas (AdminBodega, Logística).
    """
    if principal.role_name not in WAREHOUSE_SCOPED_ROLES:
        return None
    if principal.user is None:
        return []
    return list_user_warehouse_ids(db, principal.user.document_id)


def assert_warehouse_access(
    db: Session,
    principal: SecurityPrincipal,
    warehouse_id: int,
) -> None:
    allowed = resolve_allowed_warehouse_ids(db, principal)
    if allowed is None:
        return
    if int(warehouse_id) not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para esta bodega.",
        )


def enforce_query_warehouse_id(
    allowed: list[int] | None,
    warehouse_id: int | None,
) -> int | None:
    """Valida filtro explícito y devuelve warehouse_id para la consulta (o None = filtrar por lista)."""
    if allowed is None:
        return warehouse_id
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes bodegas asignadas. Contacta al administrador.",
        )
    if warehouse_id is not None:
        if int(warehouse_id) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para esta bodega.",
            )
        return int(warehouse_id)
    return None


def apply_warehouse_ids_filter(stmt, column, allowed: list[int] | None, warehouse_id: int | None):
    """Restringe un SELECT por bodega según rol y parámetro opcional."""
    effective = enforce_query_warehouse_id(allowed, warehouse_id)
    if effective is not None:
        return stmt.where(column == effective)
    if allowed is not None:
        return stmt.where(column.in_(allowed))
    return stmt
