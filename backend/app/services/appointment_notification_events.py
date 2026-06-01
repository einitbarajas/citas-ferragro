"""Publicación unificada de notificaciones de citas con actor, visibilidad y tiempo real."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import AuditLog
from app.models.user import UserRole
from app.models.user_notification import UserNotification
from app.services.appointment_actor import ActorContext, system_actor
from app.services.notification_realtime import broadcast_notification_event
from app.services.notification_service import (
    INTERNAL_STAFF_ROLES,
    _appointment_email_context,
    _dispatch_notification_emails,
    _provider_credential_email,
    _warehouse_staff_emails,
)

logger = logging.getLogger(__name__)


class AppointmentNotificationAction(str, Enum):
    created = "cita_creada"
    updated = "cita_actualizada"
    rescheduled = "cita_reprogramada"
    cancelled = "cita_cancelada"
    deleted = "cita_eliminada"
    approved = "cita_aprobada"
    rejected = "cita_rechazada"
    status_changed = "cita_estado_cambiado"
    warehouse_changed = "cita_bodega_cambiada"
    provider_changed = "cita_proveedor_cambiado"
    reminder_24h = "recordatorio_proximo"
    finalization_alert = "finalizacion_15min_alerta"
    no_presentada_auto = "no_presentada_auto"
    provider_cancelled = "cita_cancelada_proveedor"
    pending_review = "cita_para_revisar"


_STATUS_LABELS = {
    AppointmentStatus.sin_revision: "sin revisión",
    AppointmentStatus.revisado: "revisada",
    AppointmentStatus.finalizada: "finalizada",
    AppointmentStatus.no_presentada: "no presentada",
    AppointmentStatus.cancelado: "cancelada",
}


@dataclass(frozen=True)
class AppointmentSnapshot:
    id: int
    provider_id: int
    warehouse_id: int
    status: AppointmentStatus
    start_time: datetime
    duration_minutes: int


def _status_label(status: AppointmentStatus) -> str:
    return _STATUS_LABELS.get(status, status.value)


def _event_timestamp_label() -> str:
    tz = ZoneInfo(settings.business_timezone)
    return datetime.now(timezone.utc).astimezone(tz).strftime("%d/%m/%Y %H:%M")


def _detail_block(ctx, appointment_id: int, status: AppointmentStatus, *, extra: str = "") -> str:
    lines = [
        f"Fecha y hora del evento: {_event_timestamp_label()}",
        f"Número de cita: #{appointment_id}",
        f"Horario de la cita: {ctx.start_label}",
        f"Duración: {ctx.duration_minutes} min",
        f"Bodega: {ctx.warehouse_name}",
        f"Estado de la cita: {_status_label(status)}",
        f"Proveedor: {ctx.provider_name}",
    ]
    if extra.strip():
        lines.append(extra.strip())
    return "\n".join(lines)


def _verbs(action: AppointmentNotificationAction) -> tuple[str, str]:
    mapping = {
        AppointmentNotificationAction.created: ("registró", "registró"),
        AppointmentNotificationAction.pending_review: ("registró", "registró"),
        AppointmentNotificationAction.updated: ("actualizó", "actualizó"),
        AppointmentNotificationAction.rescheduled: ("reprogramó", "reprogramó"),
        AppointmentNotificationAction.cancelled: ("canceló", "canceló"),
        AppointmentNotificationAction.deleted: ("eliminó", "eliminó"),
        AppointmentNotificationAction.approved: ("aprobó", "aprobó"),
        AppointmentNotificationAction.rejected: ("rechazó", "rechazó"),
        AppointmentNotificationAction.status_changed: ("cambió el estado de", "cambió el estado de"),
        AppointmentNotificationAction.warehouse_changed: ("cambió la bodega de", "cambió la bodega de"),
        AppointmentNotificationAction.provider_changed: ("cambió el proveedor de", "cambió el proveedor de"),
        AppointmentNotificationAction.provider_cancelled: ("canceló", "canceló"),
    }
    return mapping.get(action, ("modificó", "modificó"))


def _build_staff_head(actor: ActorContext, verb: str, appointment_id: int, warehouse_name: str) -> str:
    return (
        f"{actor.actor_label.capitalize()} {verb} la cita #{appointment_id} "
        f"de la bodega {warehouse_name}."
    )


def _build_provider_head(actor: ActorContext, verb: str, appointment_id: int) -> str:
    if actor.actor_role == UserRole.proveedor:
        return f"El proveedor con NIT {actor.actor_id} {verb} la cita #{appointment_id}."
    return f"{actor.actor_label.capitalize()} {verb} la cita #{appointment_id}."


def _title_for_action(action: AppointmentNotificationAction, appointment_id: int) -> str:
    titles = {
        AppointmentNotificationAction.created: f"Cita #{appointment_id} registrada",
        AppointmentNotificationAction.pending_review: f"Cita #{appointment_id} pendiente de revisión",
        AppointmentNotificationAction.deleted: f"Cita #{appointment_id} eliminada",
        AppointmentNotificationAction.approved: f"Cita #{appointment_id} aprobada",
        AppointmentNotificationAction.rejected: f"Cita #{appointment_id} rechazada",
        AppointmentNotificationAction.cancelled: f"Cita #{appointment_id} cancelada",
        AppointmentNotificationAction.provider_cancelled: f"Cita #{appointment_id} cancelada por proveedor",
        AppointmentNotificationAction.rescheduled: f"Cita #{appointment_id} reprogramada",
    }
    return titles.get(action, f"Cita #{appointment_id} actualizada")


def _messages_for_action(
    action: AppointmentNotificationAction,
    actor: ActorContext,
    ctx,
    appointment_id: int,
    status: AppointmentStatus,
    *,
    extra: str = "",
) -> tuple[str, str, str]:
    staff_v, prov_v = _verbs(action)
    staff_head = _build_staff_head(actor, staff_v, appointment_id, ctx.warehouse_name)
    prov_head = _build_provider_head(actor, prov_v, appointment_id)
    detail = _detail_block(ctx, appointment_id, status, extra=extra)
    actor_line = f"Usuario: {actor.actor_label}\nRol: {actor.actor_role}\nAcción: {action.value}"
    staff_message = f"{staff_head}\n\n{detail}\n\n{actor_line}"
    provider_message = f"{prov_head}\n\n{detail}\n\n{actor_line}"
    title = _title_for_action(action, appointment_id)
    return title, staff_message, provider_message


def _snapshot_context(db: Session, snap: AppointmentSnapshot):
    from app.models.provider import Provider
    from app.models.warehouse import Warehouse
    from app.services.notification_service import _format_start_local

    provider = db.get(Provider, snap.provider_id)
    warehouse = db.get(Warehouse, snap.warehouse_id)

    class _Ctx:
        provider_name: str
        warehouse_name: str
        start_label: str
        duration_minutes: int

    ctx = _Ctx()
    ctx.provider_name = (
        provider.company_name.strip() if provider and provider.company_name else f"NIT {snap.provider_id}"
    )
    ctx.warehouse_name = warehouse.name.strip() if warehouse and warehouse.name else f"Bodega #{snap.warehouse_id}"
    fake = Appointment(
        provider_id=snap.provider_id,
        warehouse_id=snap.warehouse_id,
        start_time=snap.start_time,
        duration_minutes=snap.duration_minutes,
        status=snap.status,
    )
    ctx.start_label = _format_start_local(fake)
    ctx.duration_minutes = int(snap.duration_minutes)
    return ctx


def _persist_notifications(
    db: Session,
    *,
    appointment_id: int | None,
    warehouse_id: int,
    provider_id: int,
    kind: str,
    title: str,
    staff_message: str,
    provider_message: str,
    actor: ActorContext,
    action: str,
    status: AppointmentStatus,
    include_provider: bool,
) -> list[int]:
    now = datetime.now(timezone.utc)
    ids: list[int] = []
    base = dict(
        appointment_id=appointment_id,
        warehouse_id=warehouse_id,
        provider_id=provider_id,
        kind=kind,
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
        actor_label=actor.actor_label,
        action=action,
        appointment_status=status.value,
        created_at=now,
    )
    for role in INTERNAL_STAFF_ROLES:
        row = UserNotification(
            recipient_role=role,
            recipient_provider_id=None,
            title=title,
            message=staff_message,
            **base,
        )
        db.add(row)
        db.flush()
        ids.append(int(row.id))
    if include_provider:
        prow = UserNotification(
            recipient_role=UserRole.proveedor,
            recipient_provider_id=int(provider_id),
            title=title,
            message=provider_message,
            **base,
        )
        db.add(prow)
        db.flush()
        ids.append(int(prow.id))
    return ids


def _emit_realtime(
    *,
    notification_ids: list[int],
    appointment_id: int | None,
    warehouse_id: int,
    provider_id: int,
    kind: str,
    title: str,
) -> None:
    payload = {
        "type": "notification",
        "notification_ids": notification_ids,
        "appointment_id": appointment_id,
        "warehouse_id": warehouse_id,
        "provider_id": provider_id,
        "kind": kind,
        "title": title,
    }
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_notification_event(payload))
    except RuntimeError:
        try:
            asyncio.run(broadcast_notification_event(payload))
        except Exception:
            logger.debug("No se pudo emitir evento SSE", exc_info=True)


def publish_appointment_notification(
    db: Session,
    appointment: Appointment | AppointmentSnapshot,
    *,
    action: AppointmentNotificationAction,
    actor: ActorContext | None = None,
    include_provider: bool = True,
    extra_detail: str = "",
    send_email: bool = True,
) -> list[int]:
    actor = actor or system_actor()
    appt_id = int(appointment.id)
    warehouse_id = int(appointment.warehouse_id)
    provider_id = int(appointment.provider_id)
    status = appointment.status

    if isinstance(appointment, Appointment):
        ctx = _appointment_email_context(db, appointment)
        persist_appointment_id: int | None = appt_id
    else:
        ctx = _snapshot_context(db, appointment)
        persist_appointment_id = None

    title, staff_message, provider_message = _messages_for_action(
        action, actor, ctx, appt_id, status, extra=extra_detail
    )
    kind = action.value

    notification_ids = _persist_notifications(
        db,
        appointment_id=persist_appointment_id,
        warehouse_id=warehouse_id,
        provider_id=provider_id,
        kind=kind,
        title=title,
        staff_message=staff_message,
        provider_message=provider_message,
        actor=actor,
        action=kind,
        status=status,
        include_provider=include_provider,
    )

    if send_email:
        staff_emails = _warehouse_staff_emails(db, warehouse_id)
        provider_email = _provider_credential_email(db, provider_id) if include_provider else None
        if provider_email and provider_message != staff_message:
            if staff_emails:
                _dispatch_notification_emails(staff_emails, title=title, message=staff_message)
            _dispatch_notification_emails([provider_email], title=title, message=provider_message)
        else:
            emails = list(staff_emails)
            if provider_email:
                emails.append(provider_email)
            if emails:
                _dispatch_notification_emails(emails, title=title, message=staff_message)

    _emit_realtime(
        notification_ids=notification_ids,
        appointment_id=persist_appointment_id,
        warehouse_id=warehouse_id,
        provider_id=provider_id,
        kind=kind,
        title=title,
    )
    return notification_ids


def record_audit(
    db: Session,
    *,
    appointment_id: int,
    actor: ActorContext,
    action: str,
    description: str,
    critical_field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor.actor_id,
            appointment_id=appointment_id,
            action=action,
            description=description,
            created_at=datetime.now(timezone.utc),
            critical_field=critical_field,
            old_value=old_value,
            new_value=new_value,
            ip_address=actor.ip_address,
        )
    )


def notify_status_change(
    db: Session,
    appointment: Appointment,
    *,
    actor: ActorContext,
    old_status: AppointmentStatus,
    new_status: AppointmentStatus,
    extra_detail: str = "",
) -> None:
    if new_status == AppointmentStatus.revisado and old_status == AppointmentStatus.sin_revision:
        action = AppointmentNotificationAction.approved
    elif new_status == AppointmentStatus.cancelado:
        if actor.actor_role == UserRole.proveedor:
            action = AppointmentNotificationAction.provider_cancelled
        elif old_status == AppointmentStatus.sin_revision:
            action = AppointmentNotificationAction.rejected
        else:
            action = AppointmentNotificationAction.cancelled
    else:
        action = AppointmentNotificationAction.status_changed
    extra = f"Estado anterior: {_status_label(old_status)}. Estado nuevo: {_status_label(new_status)}."
    if extra_detail.strip():
        extra = f"{extra}\n{extra_detail.strip()}"
    publish_appointment_notification(
        db, appointment, action=action, actor=actor, extra_detail=extra, include_provider=True
    )


def resolve_update_action(updates: dict) -> AppointmentNotificationAction:
    if "start_time" in updates:
        return AppointmentNotificationAction.rescheduled
    if "warehouse_id" in updates:
        return AppointmentNotificationAction.warehouse_changed
    if "provider_id" in updates:
        return AppointmentNotificationAction.provider_changed
    if "status" in updates:
        return AppointmentNotificationAction.status_changed
    return AppointmentNotificationAction.updated
