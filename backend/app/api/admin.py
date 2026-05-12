from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.audit_log import AuditLog
from app.models.user import UserRole
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logs", response_model=list[AuditLogOut])
def list_logs(
    db: Session = Depends(get_db),
    _: object = Depends(require_roles(UserRole.admin)),
):
    logs = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc())).scalars().all()
    return logs
