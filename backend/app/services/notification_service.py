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
    """Correos Admin en BD + admin de bootstrap (p. ej. ebarajas@ferragro.com)."""
    emails = _staff_emails_for_role(db, UserRole.admin)
    bootstrap = str(settings.admin_bootstrap_email or "").strip()
    if bootstrap:
        emails = dedupe_emails([*emails, bootstrap])
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
    staff_message: str | None = None,
    provider_message: str | None = None,
    include_provider: bool = True,
) -> None:
    """Admin global, staff de la bodega (Logística + AdminBodega) y proveedor."""
    staff_body = staff_message or message
    provider_body = provider_message or message
    _persist_staff_in_app_notifications(
        db, appointment, kind=kind, title=title, message=staff_body
    )
    staff_emails = _warehouse_staff_emails(db, int(appointment.warehouse_id))
    provider_email: str | None = None
    if include_provider:
        _persist_provider_in_app_notification(
            db, appointment, kind=kind, title=title, message=provider_body
        )
        provider_email = _provider_credential_email(db, int(appointment.provider_id))
        if not provider_email:
            logger.warning(
                "Aviso cita #%s (%s): proveedor %s sin correo en credencial",
                appointment.id,
                kind,
                appointment.provider_id,
            )

    if not staff_emails:
        logger.warning(
            "Aviso cita #%s (%s): sin correos de staff para bodega %s",
            appointment.id,
            kind,
            appointment.warehouse_id,
        )

    if provider_email and provider_body != staff_body:
        if staff_emails:
            dispatch_notification_emails_batch(
                staff_emails, title=title, message=staff_body
            )
        dispatch_notification_emails_batch(
            [provider_email], title=title, message=provider_body
        )
    else:
        all_emails = list(staff_emails)
        if provider_email:
            all_emails.append(provider_email)
        if all_emails:
            dispatch_notification_emails_batch(
                all_emails, title=title, message=staff_body
            )


def notify_staff_review_needed(db: Session, appointment: Appointment) -> None:
    if appointment.status != AppointmentStatus.sin_revision:
        return
    ctx = _appointment_email_context(db, appointment)
    title = f"Cita #{appointment.id} pendiente de revisión"
    staff_message = (
        f"El proveedor {ctx.provider_name} agendó una cita nueva para revisar.\n"
        f"Horario: {ctx.start_label} (duración {ctx.duration_minutes} min).\n"
        f"Bodega: {ctx.warehouse_name}.\n"
        "Entra a Revisión de citas o Buscar citas para atenderla."
    )
    provider_message = (
        f"Registraste la cita #{appointment.id} en Ferragro; queda pendiente de revisión.\n"
        f"Horario: {ctx.start_label} (duración {ctx.duration_minutes} min).\n"
        f"Bodega: {ctx.warehouse_name}.\n"
        "Te avisaremos por correo cuando sea confirmada o si requiere cambios."
    )
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="cita_para_revisar",
        title=title,
        message=staff_message,
        staff_message=staff_message,
        provider_message=provider_message,
        include_provider=True,
    )


def notify_provider_appointment_updated(
    db: Session,
    appointment: Appointment,
    *,
    summary: str,
) -> None:
    """Aviso por correo e in-app cuando staff o el sistema actualiza una cita."""
    ctx = _appointment_email_context(db, appointment)
    title = f"Cita #{appointment.id} fue actualizada"
    staff_message = (
        f"{summary.strip()}\n"
        f"Proveedor: {ctx.provider_name}.\n"
        f"Horario actual: {ctx.start_label} (duración {ctx.duration_minutes} min).\n"
        f"Bodega: {ctx.warehouse_name}.\n"
        "Revisa Revisión de citas o Buscar citas en el panel."
    )
    provider_message = (
        f"{summary.strip()}\n"
        f"Horario actual: {ctx.start_label} (duración {ctx.duration_minutes} min).\n"
        f"Bodega: {ctx.warehouse_name}.\n"
        "Revisa el panel de Ferragro para ver el detalle."
    )
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="cita_actualizada",
        title=title,
        message=staff_message,
        staff_message=staff_message,
        provider_message=provider_message,
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
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="finalizacion_15min_alerta",
        title=title,
        message=message,
        include_provider=False,
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
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="recordatorio_proximo",
        title=title,
        message=message,
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
    _notify_appointment_stakeholders(
        db,
        appointment,
        kind="no_presentada_auto",
        title=title,
        message=message,
        include_provider=False,
    )
