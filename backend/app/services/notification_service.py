from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.credential import Credential
from app.models.provider import Provider
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.user_notification import UserNotification
from app.models.user_warehouse import UserWarehouse
from app.services.email_dispatch import dispatch_notification_email

WAREHOUSE_SCOPED_STAFF_ROLES = (UserRole.logistica, UserRole.admin_bodega)
INTERNAL_STAFF_ROLES = (UserRole.admin,) + WAREHOUSE_SCOPED_STAFF_ROLES


def _format_start_local(appointment: Appointment) -> str:
    tz = ZoneInfo(settings.business_timezone)
    return appointment.start_time.astimezone(tz).strftime("%d/%m/%Y %H:%M")


def _dedupe_emails(emails: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for email in emails:
        normalized = str(email or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _staff_emails_for_role(db: Session, role_name: str) -> list[str]:
    rows = db.execute(
        select(Credential.email)
        .join(User, User.credential_id == Credential.id)
        .join(Role, User.role_id == Role.id)
        .where(Role.name == role_name)
    ).scalars().all()
    return _dedupe_emails([str(email) for email in rows])


def _staff_emails_for_warehouse_role(db: Session, warehouse_id: int, role_name: str) -> list[str]:
    rows = db.execute(
        select(Credential.email)
        .join(User, User.credential_id == Credential.id)
        .join(Role, User.role_id == Role.id)
        .join(UserWarehouse, UserWarehouse.document_id == User.document_id)
        .where(Role.name == role_name, UserWarehouse.warehouse_id == int(warehouse_id))
    ).scalars().all()
    return _dedupe_emails([str(email) for email in rows])


def _warehouse_staff_emails(db: Session, warehouse_id: int) -> list[str]:
    emails: list[str] = []
    emails.extend(_staff_emails_for_role(db, UserRole.admin))
    for role in WAREHOUSE_SCOPED_STAFF_ROLES:
        emails.extend(_staff_emails_for_warehouse_role(db, warehouse_id, role))
    return _dedupe_emails(emails)


def _provider_credential_email(db: Session, provider_id: int) -> str | None:
    provider = db.get(Provider, provider_id)
    if not provider:
        return None
    email = provider.credential.email if provider.credential else provider.company_email
    normalized = str(email or "").strip()
    return normalized or None


def _appointment_stakeholder_emails(
    db: Session,
    appointment: Appointment,
    *,
    include_provider: bool = True,
) -> list[str]:
    emails = _warehouse_staff_emails(db, int(appointment.warehouse_id))
    if include_provider:
        provider_email = _provider_credential_email(db, int(appointment.provider_id))
        if provider_email:
            emails = _dedupe_emails(emails + [provider_email])
    return emails


def _dispatch_notification_emails(to_emails: list[str], *, title: str, message: str) -> None:
    for to_email in _dedupe_emails(to_emails):
        dispatch_notification_email(to_email, title, message)


def _persist_staff_in_app_notifications(
    db: Session,
    appointment: Appointment,
    *,
    kind: str,
    title: str,
    message: str,
) -> None:
    now = datetime.now(timezone.utc)
    for role in INTERNAL_STAFF_ROLES:
        db.add(
            UserNotification(
                recipient_role=role,
                recipient_provider_id=None,
                appointment_id=appointment.id,
                kind=kind,
                title=title,
                message=message,
                created_at=now,
            )
        )


def _persist_provider_in_app_notification(
    db: Session,
    appointment: Appointment,
    *,
    kind: str,
    title: str,
    message: str,
) -> None:
    db.add(
        UserNotification(
            recipient_role=UserRole.proveedor,
            recipient_provider_id=int(appointment.provider_id),
            appointment_id=appointment.id,
            kind=kind,
            title=title,
            message=message,
            created_at=datetime.now(timezone.utc),
        )
    )


def _notify_appointment_stakeholders(
    db: Session,
    appointment: Appointment,
    *,
    kind: str,
    title: str,
    message: str,
    include_provider: bool = True,
) -> None:
    """Admin global, staff de la bodega (Logística + AdminBodega) y proveedor."""
    _persist_staff_in_app_notifications(db, appointment, kind=kind, title=title, message=message)
    if include_provider:
        _persist_provider_in_app_notification(db, appointment, kind=kind, title=title, message=message)
    _dispatch_notification_emails(
        _appointment_stakeholder_emails(db, appointment, include_provider=include_provider),
        title=title,
        message=message,
    )


def notify_staff_review_needed(db: Session, appointment: Appointment) -> None:
    if appointment.status != AppointmentStatus.sin_revision:
        return
    start_label = _format_start_local(appointment)
    title = f"Cita #{appointment.id} pendiente de revisión"
    message = (
        f"Hay una cita nueva o actualizada para revisar. Inicio: {start_label}. "
        "Entra a Revisión de citas o Buscar citas para atenderla."
    )
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="cita_para_revisar",
        title=title,
        message=message,
        include_provider=True,
    )


def notify_provider_appointment_updated(
    db: Session,
    appointment: Appointment,
    *,
    summary: str,
) -> None:
    start_label = _format_start_local(appointment)
    title = f"Cita #{appointment.id} fue actualizada"
    message = (
        f"{summary} Inicio actual: {start_label}. "
        "Revisa el panel de Ferragro para ver el detalle."
    )
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="cita_actualizada",
        title=title,
        message=message,
        include_provider=True,
    )


def notify_staff_provider_cancelled(
    db: Session,
    appointment: Appointment,
    *,
    reason: str,
    provider_label: str | None = None,
) -> None:
    start_label = _format_start_local(appointment)
    label = (provider_label or "").strip() or f"NIT {appointment.provider_id}"
    title = f"Cita #{appointment.id} cancelada por el proveedor"
    message = (
        f"{label} canceló la cita que estaba programada para {start_label}. "
        f"Motivo indicado: {reason.strip()}"
    )
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="cita_cancelada_proveedor",
        title=title,
        message=message,
        include_provider=True,
    )
