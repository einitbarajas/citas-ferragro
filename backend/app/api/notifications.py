import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from starlette import status

from app.api.deps import SecurityPrincipal, get_db, require_roles
from app.core.config import settings
from app.core.responses import ok_response
from app.models.appointment import Appointment
from app.models.user import User, UserRole
from app.models.notification_read import NotificationRead
from app.models.user_notification import UserNotification
from app.services.auth_sessions import credential_id_for_subject, get_active_refresh_session
from app.services.notification_realtime import subscribe_user, unsubscribe_user
from app.services.warehouse_scope import list_user_warehouse_ids

router = APIRouter(prefix="/notifications", tags=["notifications"])

NOTIFICATION_ROLES = (
    UserRole.admin,
    UserRole.logistica,
    UserRole.admin_bodega,
    UserRole.proveedor,
)


def _reader_id(principal: SecurityPrincipal) -> str:
    return str(principal.subject)


def _read_map_for_rows(db: Session, reader_id: str, notification_ids: list[int]) -> dict[int, datetime]:
    if not notification_ids:
        return {}
    rows = db.execute(
        select(NotificationRead.notification_id, NotificationRead.read_at).where(
            NotificationRead.reader_id == reader_id,
            NotificationRead.notification_id.in_(notification_ids),
        )
    ).all()
    return {int(nid): read_at for nid, read_at in rows}


def _serialize_notification(row: UserNotification, *, read_at: datetime | None = None) -> dict:
    return {
        "id": row.id,
        "appointment_id": row.appointment_id,
        "warehouse_id": row.warehouse_id,
        "provider_id": int(row.provider_id) if row.provider_id is not None else None,
        "kind": row.kind,
        "action": row.action or row.kind,
        "title": row.title,
        "message": row.message,
        "actor_id": row.actor_id,
        "actor_role": row.actor_role,
        "actor_label": row.actor_label,
        "appointment_status": row.appointment_status,
        "read": read_at is not None,
        "read_at": read_at,
        "created_at": row.created_at,
    }


def _scoped_warehouse_clause(allowed: list[int]):
    return or_(
        UserNotification.warehouse_id.in_(allowed),
        UserNotification.appointment_id.in_(
            select(Appointment.id).where(Appointment.warehouse_id.in_(allowed))
        ),
    )


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
        return stmt.where(
            UserNotification.recipient_role == role,
            _scoped_warehouse_clause(allowed),
        )
    raise HTTPException(status_code=403, detail="Rol no autorizado para notificaciones")


def _principal_from_access_token(token: str, db: Session) -> SecurityPrincipal:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = str(payload.get("sub") or "")
        role_name = str(payload.get("role") or "")
        token_type = str(payload.get("token_type") or "")
        jti_raw = str(payload.get("jti") or "")
        exp = payload.get("exp")
        if not subject or not role_name:
            raise credentials_exception
        if token_type and token_type != "access":
            raise credentials_exception
        if not jti_raw:
            raise credentials_exception
        session_jti = UUID(jti_raw)
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise credentials_exception
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    cred_id = credential_id_for_subject(db, subject, role_name)
    if cred_id is None:
        raise credentials_exception
    if not get_active_refresh_session(db, cred_id, session_jti):
        raise credentials_exception

    if role_name in (UserRole.proveedor, "Proveedor"):
        from app.models.provider import Provider, ProviderAccountStatus

        try:
            nit = int(subject)
        except ValueError:
            raise credentials_exception
        provider = db.get(Provider, nit)
        if not provider or provider.status == ProviderAccountStatus.suspendido:
            raise credentials_exception
        return SecurityPrincipal(subject=str(nit), role_name=UserRole.proveedor, provider=provider)

    user = db.get(User, subject)
    if not user:
        raise credentials_exception
    return SecurityPrincipal(subject=subject, role_name=role_name, user=user)


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
    reader_id = _reader_id(principal)
    read_subq = select(NotificationRead.notification_id).where(NotificationRead.reader_id == reader_id)
    if unread_only:
        stmt = stmt.where(UserNotification.id.not_in(read_subq))
    elif read_only:
        stmt = stmt.where(UserNotification.id.in_(read_subq))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    base_ids = _recipient_filter(select(UserNotification.id), principal, db)
    unread_total = db.scalar(
        select(func.count()).select_from(
            base_ids.where(UserNotification.id.not_in(read_subq)).subquery()
        )
    ) or 0
    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
    read_map = _read_map_for_rows(db, reader_id, [int(r.id) for r in rows])
    return ok_response(
        {
            "items": [_serialize_notification(row, read_at=read_map.get(int(row.id))) for row in rows],
            "total": total,
            "unread_total": unread_total,
            "page": page,
            "page_size": page_size,
        },
        "Notificaciones obtenidas",
    )


@router.get("/stream")
async def stream_notifications(
    token: str = Query(..., description="JWT de acceso"),
    db: Session = Depends(get_db),
):
    principal = _principal_from_access_token(token, db)
    if principal.role_name not in NOTIFICATION_ROLES:
        raise HTTPException(status_code=403, detail="Rol no autorizado")

    warehouse_ids: frozenset[int] = frozenset()
    if principal.role_name in (UserRole.logistica, UserRole.admin_bodega) and principal.user:
        warehouse_ids = frozenset(list_user_warehouse_ids(db, principal.user.document_id))

    subject = (
        str(principal.subject)
        if principal.role_name == UserRole.proveedor
        else str(principal.document_id)
    )
    queue = await subscribe_user(
        role=principal.role_name,
        subject=subject,
        warehouse_ids=warehouse_ids,
    )

    async def event_generator():
        try:
            yield ": connected\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await unsubscribe_user(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
    reader_id = _reader_id(principal)
    read_subq = select(NotificationRead.notification_id).where(NotificationRead.reader_id == reader_id)
    stmt = _recipient_filter(select(UserNotification), principal, db).where(UserNotification.id.not_in(read_subq))
    rows = db.execute(stmt).scalars().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        db.add(NotificationRead(notification_id=int(row.id), reader_id=reader_id, read_at=now))
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
    reader_id = _reader_id(principal)
    existing = db.execute(
        select(NotificationRead).where(
            NotificationRead.notification_id == row.id,
            NotificationRead.reader_id == reader_id,
        )
    ).scalar_one_or_none()
    read_at = existing.read_at if existing else None
    if existing is None:
        read_at = datetime.now(timezone.utc)
        db.add(
            NotificationRead(
                notification_id=int(row.id),
                reader_id=reader_id,
                read_at=read_at,
            )
        )
        db.commit()
    return ok_response(_serialize_notification(row, read_at=read_at), "Notificación marcada como leída")
