from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import SecurityPrincipal, get_db, require_roles
from app.core.responses import ok_response
from app.models.appointment import Appointment
from app.models.user import UserRole
from app.models.user_notification import UserNotification
from app.services.warehouse_scope import list_user_warehouse_ids

router = APIRouter(prefix="/notifications", tags=["notifications"])

NOTIFICATION_ROLES = (
    UserRole.admin,
    UserRole.logistica,
    UserRole.admin_bodega,
    UserRole.proveedor,
)


def _serialize_notification(row: UserNotification) -> dict:
    return {
        "id": row.id,
        "appointment_id": row.appointment_id,
        "kind": row.kind,
        "title": row.title,
        "message": row.message,
        "read": row.read_at is not None,
        "read_at": row.read_at,
        "created_at": row.created_at,
    }


def _recipient_filter(stmt, principal: SecurityPrincipal, db: Session):
    role = principal.role_name
    if role == UserRole.proveedor:
        return stmt.where(
            UserNotification.recipient_role == UserRole.proveedor,
            UserNotification.recipient_provider_id == int(principal.subject),
        )
    if role == UserRole.admin:
        return stmt.where(UserNotification.recipient_role == UserRole.admin)
    if role in (UserRole.logistica, UserRole.admin_bodega):
        if principal.user is None:
            raise HTTPException(status_code=403, detail="Usuario no encontrado")
        allowed = list_user_warehouse_ids(db, principal.user.document_id)
        if not allowed:
            return stmt.where(UserNotification.id == -1)
        return (
            stmt.join(Appointment, UserNotification.appointment_id == Appointment.id)
            .where(
                UserNotification.recipient_role == role,
                Appointment.warehouse_id.in_(allowed),
            )
        )
    raise HTTPException(status_code=403, detail="Rol no autorizado para notificaciones")


@router.get("/")
@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    read_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(*NOTIFICATION_ROLES)),
):
    if unread_only and read_only:
        raise HTTPException(status_code=400, detail="No se puede filtrar por leídas y no leídas a la vez")
    stmt = select(UserNotification).order_by(UserNotification.created_at.desc(), UserNotification.id.desc())
    stmt = _recipient_filter(stmt, principal, db)
    if unread_only:
        stmt = stmt.where(UserNotification.read_at.is_(None))
    elif read_only:
        stmt = stmt.where(UserNotification.read_at.isnot(None))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    unread_stmt = _recipient_filter(select(func.count()).select_from(UserNotification), principal, db).where(
        UserNotification.read_at.is_(None)
    )
    unread_total = db.scalar(unread_stmt) or 0
    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
    return ok_response(
        {
            "items": [_serialize_notification(row) for row in rows],
            "total": total,
            "unread_total": unread_total,
            "page": page,
            "page_size": page_size,
        },
        "Notificaciones obtenidas",
    )


@router.delete("/all")
def delete_all_notifications(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(*NOTIFICATION_ROLES)),
):
    stmt = _recipient_filter(select(UserNotification), principal, db)
    rows = db.execute(stmt).scalars().all()
    for row in rows:
        db.delete(row)
    if rows:
        db.commit()
    return ok_response({"deleted": len(rows)}, "Notificaciones eliminadas")


@router.patch("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(*NOTIFICATION_ROLES)),
):
    stmt = _recipient_filter(select(UserNotification), principal, db).where(UserNotification.read_at.is_(None))
    rows = db.execute(stmt).scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read_at = now
    if rows:
        db.commit()
    return ok_response({"updated": len(rows)}, "Notificaciones marcadas como leídas")


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_roles(*NOTIFICATION_ROLES)),
):
    stmt = select(UserNotification).where(UserNotification.id == notification_id)
    stmt = _recipient_filter(stmt, principal, db)
    row = db.execute(stmt).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return ok_response(_serialize_notification(row), "Notificación marcada como leída")
