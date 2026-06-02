import logging
from dataclasses import dataclass
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
from app.models.warehouse import Warehouse
from app.services.email_dispatch import dispatch_notification_emails_batch
from app.services.email_utils import dedupe_emails

logger = logging.getLogger(__name__)

WAREHOUSE_SCOPED_STAFF_ROLES = (UserRole.logistica, UserRole.admin_bodega)
INTERNAL_STAFF_ROLES = (UserRole.admin,) + WAREHOUSE_SCOPED_STAFF_ROLES


def _format_start_local(appointment: Appointment) -> str:
    tz = ZoneInfo(settings.business_timezone)
    return appointment.start_time.astimezone(tz).strftime("%d/%m/%Y %H:%M")


@dataclass(frozen=True)
class _AppointmentEmailContext:
    provider_name: str
    warehouse_name: str
    start_label: str
    duration_minutes: int


def _appointment_email_context(db: Session, appointment: Appointment) -> _AppointmentEmailContext:
    provider = db.get(Provider, int(appointment.provider_id))
    provider_name = (provider.company_name.strip() if provider and provider.company_name else "") or (
        f"Proveedor NIT {appointment.provider_id}"
    )
    warehouse = db.get(Warehouse, int(appointment.warehouse_id))
    warehouse_name = (warehouse.name.strip() if warehouse and warehouse.name else "") or (
        f"Bodega #{appointment.warehouse_id}"
    )
    return _AppointmentEmailContext(
        provider_name=provider_name,
        warehouse_name=warehouse_name,
        start_label=_format_start_local(appointment),
        duration_minutes=int(appointment.duration_minutes or 90),
    )


def admin_notification_emails(db: Session) -> list[str]:
    """Correos de usuarios con rol Admin registrados en BD.

    El admin_bootstrap_email se añade SOLO como fallback cuando no existe ningún
    Admin en la base de datos. Esto evita que un email hardcodeado reciba todas
    las notificaciones de todas las bodegas sin ser un Admin real.
    """
    emails = _staff_emails_for_role(db, UserRole.admin)
    if not emails:
        bootstrap = str(settings.admin_bootstrap_email or "").strip()
        if bootstrap:
            logger.info(
                "No hay Admins en BD — usando admin_bootstrap_email (%s) como fallback",
                bootstrap,
            )
            emails = dedupe_emails([bootstrap])
    return emails


def _staff_emails_for_role(db: Session, role_name: str) -> list[str]:
    rows = db.execute(
        select(Credential.email)
        .join(User, User.credential_id == Credential.id)
        .join(Role, User.role_id == Role.id)
        .where(Role.name == role_name)
    ).scalars().all()
    return dedupe_emails([str(email) for email in rows])


def _staff_emails_for_warehouse_role(db: Session, warehouse_id: int, role_name: str) -> list[str]:
    rows = db.execute(
        select(Credential.email)
        .join(User, User.credential_id == Credential.id)
        .join(Role, User.role_id == Role.id)
        .join(UserWarehouse, UserWarehouse.document_id == User.document_id)
        .where(Role.name == role_name, UserWarehouse.warehouse_id == int(warehouse_id))
    ).scalars().all()
    return dedupe_emails([str(email) for email in rows])


def _warehouse_staff_emails(db: Session, warehouse_id: int) -> list[str]:
    emails: list[str] = []
    emails.extend(admin_notification_emails(db))
    for role in WAREHOUSE_SCOPED_STAFF_ROLES:
        emails.extend(_staff_emails_for_warehouse_role(db, warehouse_id, role))
    return dedupe_emails(emails)


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
            emails = dedupe_emails(emails + [provider_email])
    return emails


def _dispatch_notification_emails(to_emails: list[str], *, title: str, message: str) -> None:
    dispatch_notification_emails_batch(to_emails, title=title, message=message)


def notify_staff_review_needed(
    db: Session,
    appointment: Appointment,
    *,
    actor=None,
) -> None:
    from app.services.appointment_actor import system_actor
    from app.services.appointment_notification_events import (
        AppointmentNotificationAction,
        publish_appointment_notification,
    )

    if appointment.status != AppointmentStatus.sin_revision:
        return
    publish_appointment_notification(
        db,
        appointment,
        action=AppointmentNotificationAction.pending_review,
        actor=actor or system_actor(),
        include_provider=True,
    )


def notify_provider_appointment_updated(
    db: Session,
    appointment: Appointment,
    *,
    summary: str,
    actor=None,
    action=None,
) -> None:
    from app.services.appointment_actor import system_actor
    from app.services.appointment_notification_events import (
        AppointmentNotificationAction,
        publish_appointment_notification,
    )

    publish_appointment_notification(
        db,
        appointment,
        action=action or AppointmentNotificationAction.updated,
        actor=actor or system_actor(),
        extra_detail=summary.strip(),
        include_provider=True,
    )


def notify_staff_provider_cancelled(
    db: Session,
    appointment: Appointment,
    *,
    reason: str,
    actor=None,
) -> None:
    from app.services.appointment_actor import system_actor
    from app.services.appointment_notification_events import (
        AppointmentNotificationAction,
        publish_appointment_notification,
    )

    extra = f"Motivo: {reason.strip()}"
    publish_appointment_notification(
        db,
        appointment,
        action=AppointmentNotificationAction.provider_cancelled,
        actor=actor or system_actor(),
        extra_detail=extra,
        include_provider=True,
    )


def _format_deadline_local(deadline_utc: datetime) -> str:
    tz = ZoneInfo(settings.business_timezone)
    aware = deadline_utc if deadline_utc.tzinfo else deadline_utc.replace(tzinfo=timezone.utc)
    return aware.astimezone(tz).strftime("%d/%m/%Y %H:%M")


def notify_staff_finalization_window_started(
    db: Session,
    appointment: Appointment,
    *,
    deadline_utc: datetime,
) -> None:
    """Avisa a staff que la cita ya inició y tienen 15 min para marcar finalizada."""
    if appointment.status != AppointmentStatus.revisado:
        return
    start_label = _format_start_local(appointment)
    deadline_label = _format_deadline_local(deadline_utc)
    title = f"Cita #{appointment.id}: marcar finalizada en los próximos 15 min"
    message = (
        f"La cita revisada programada para {start_label} ya está en curso. "
        f"Tienes hasta {deadline_label} ({settings.business_timezone}) para marcarla como finalizada "
        "en el sistema. Si no se marca a tiempo, pasará automáticamente a no presentada."
    )
    from app.services.appointment_actor import system_actor
    from app.services.appointment_notification_events import (
        AppointmentNotificationAction,
        publish_appointment_notification,
    )

    publish_appointment_notification(
        db,
        appointment,
        action=AppointmentNotificationAction.finalization_alert,
        actor=system_actor(),
        extra_detail=message,
        include_provider=False,
        send_email=True,
    )


def notify_warehouse_schedule_updated(
    db: Session,
    *,
    warehouse_id: int,
    summary: str,
    actor_label: str,
) -> None:
    """
    Aviso por correo al guardar franjas (semanales, por fecha o lote).
    No crea notificación in-app: el modelo exige IdCita y las franjas no tienen cita.
    """
    title = "Horarios de agendamiento actualizados"
    message = (
        f"{summary}\n\n"
        f"Acción realizada por: {actor_label}.\n"
        "Revisa el panel Ferragro en Franjas horarias."
    )
    emails = _warehouse_staff_emails(db, warehouse_id)
    logger.info("Aviso de franjas horarias: %d destinatario(s)", len(emails))
    _dispatch_notification_emails(emails, title=title, message=message)


def notify_appointment_reminder_24h(db: Session, appointment: Appointment) -> None:
    """Recordatorio por correo ~24 h antes del inicio de la cita."""
    start_label = _format_start_local(appointment)
    title = f"Recordatorio: cita #{appointment.id} en 24 horas"
    message = (
        f"Tu cita en Ferragro está programada para {start_label}. "
        "Revisa el panel para confirmar horario, bodega y detalles de entrega."
    )
    from app.services.appointment_actor import system_actor
    from app.services.appointment_notification_events import (
        AppointmentNotificationAction,
        publish_appointment_notification,
    )

    publish_appointment_notification(
        db,
        appointment,
        action=AppointmentNotificationAction.reminder_24h,
        actor=system_actor(),
        extra_detail=message,
        include_provider=True,
    )


def notify_staff_no_presentada_auto(db: Session, appointment: Appointment) -> None:
    """Avisa a staff que la cita pasó a no presentada por vencimiento de la ventana."""
    start_label = _format_start_local(appointment)
    title = f"Cita #{appointment.id} marcada automáticamente como no presentada"
    message = (
        f"La cita revisada de {start_label} no fue marcada como finalizada dentro de los "
        "15 minutos posteriores a la hora de la cita. El sistema la registró como no presentada."
    )
    from app.services.appointment_actor import system_actor
    from app.services.appointment_notification_events import (
        AppointmentNotificationAction,
        publish_appointment_notification,
    )

    publish_appointment_notification(
        db,
        appointment,
        action=AppointmentNotificationAction.no_presentada_auto,
        actor=system_actor(),
        extra_detail=message,
        include_provider=False,
    )
