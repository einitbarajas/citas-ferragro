"""Scheduler: ventana de 15 min para marcar finalizada; luego no presentada automática."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.audit_log import ChangeLog
from app.models.reminder_run import ReminderExecution
from app.services.notification_service import (
    notify_staff_finalization_window_started,
    notify_staff_no_presentada_auto,
)

logger = logging.getLogger(__name__)

KIND_ALERTA = "finalizacion_15min_alerta"
KIND_AUTO_NO_PRESENTADA = "no_presentada_auto"
SYSTEM_ACTOR_ID = "sistema"


def _grace_minutes() -> int:
    return max(1, int(settings.appointment_finalization_grace_minutes))


def _reminder_exists(db: Session, appointment_id: int, kind: str) -> bool:
    return (
        db.execute(
            select(ReminderExecution.id).where(
                ReminderExecution.appointment_id == appointment_id,
                ReminderExecution.kind == kind,
            ).limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _record_reminder(
    db: Session,
    appointment_id: int,
    kind: str,
    *,
    detail: str,
    executed_at: datetime,
) -> None:
    db.add(
        ReminderExecution(
            appointment_id=appointment_id,
            kind=kind,
            status="registrado",
            detail=detail,
            executed_at=executed_at,
        )
    )


def _process_alerts(db: Session, now: datetime, grace: timedelta) -> int:
    """Citas revisadas en ventana [start_time, start_time + grace): enviar alerta una vez."""
    window_start = now - grace
    appointments = (
        db.execute(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.revisado,
                Appointment.start_time <= now,
                Appointment.start_time > window_start,
            )
        )
        .scalars()
        .all()
    )
    sent = 0
    for appt in appointments:
        if _reminder_exists(db, appt.id, KIND_ALERTA):
            continue
        deadline = appt.start_time + grace
        notify_staff_finalization_window_started(db, appt, deadline_utc=deadline)
        _record_reminder(
            db,
            appt.id,
            KIND_ALERTA,
            detail=(
                f"Alerta ventana de {grace.total_seconds() // 60} min para marcar finalizada "
                f"(deadline UTC {deadline.isoformat()})."
            ),
            executed_at=now,
        )
        sent += 1
    return sent


def _process_auto_no_presentada(db: Session, now: datetime, grace: timedelta) -> int:
    """Citas revisadas con start_time + grace <= now: marcar no presentada una vez."""
    cutoff = now - grace
    appointments = (
        db.execute(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.revisado,
                Appointment.start_time <= cutoff,
            )
        )
        .scalars()
        .all()
    )
    updated = 0
    for appt in appointments:
        if _reminder_exists(db, appt.id, KIND_AUTO_NO_PRESENTADA):
            continue
        old_status = appt.status
        appt.status = AppointmentStatus.no_presentada
        db.add(
            ChangeLog(
                actor_id=SYSTEM_ACTOR_ID,
                appointment_id=appt.id,
                action="auto_no_presentada",
                description=(
                    f"Estado cambiado automáticamente de {old_status.value} a no_presentada "
                    f"tras {grace.total_seconds() // 60} min sin marcar finalizada."
                ),
                created_at=now,
                critical_field="estado",
                old_value=old_status.value,
                new_value=AppointmentStatus.no_presentada.value,
            )
        )
        notify_staff_no_presentada_auto(db, appt)
        _record_reminder(
            db,
            appt.id,
            KIND_AUTO_NO_PRESENTADA,
            detail="Cierre automático por vencimiento de ventana de finalización.",
            executed_at=now,
        )
        updated += 1
    return updated


def run_no_presentada_batch() -> tuple[int, int]:
    """Ejecuta alertas y auto-cierres. Retorna (alertas_enviadas, citas_actualizadas)."""
    now = datetime.now(timezone.utc)
    grace = timedelta(minutes=_grace_minutes())
    alerts = 0
    closed = 0
    with SessionLocal() as db:
        alerts = _process_alerts(db, now, grace)
        closed = _process_auto_no_presentada(db, now, grace)
        if alerts or closed:
            db.commit()
    return alerts, closed


async def no_presentada_scheduler_loop(stop_event: asyncio.Event) -> None:
    interval = max(30, int(settings.no_presentada_scheduler_interval_seconds))
    while True:
        try:
            alerts, closed = run_no_presentada_batch()
            if alerts or closed:
                logger.info(
                    "Scheduler no presentada: alertas=%s, auto_cerradas=%s",
                    alerts,
                    closed,
                )
        except Exception:
            logger.exception("Error en scheduler de no presentada")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
