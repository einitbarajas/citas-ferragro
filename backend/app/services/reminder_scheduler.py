"""Tareas programadas en segundo plano (recordatorios de citas)."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.reminder_run import ReminderExecution

logger = logging.getLogger(__name__)


def run_reminder_batch() -> int:
    """Registra recordatorios para citas que inician en ~24 h (ventana 23–25 h)."""
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    inserted = 0
    with SessionLocal() as db:
        appointments = (
            db.execute(
                select(Appointment).where(
                    Appointment.start_time >= window_start,
                    Appointment.start_time <= window_end,
                    Appointment.status.in_([AppointmentStatus.sin_revision, AppointmentStatus.revisado]),
                )
            )
            .scalars()
            .all()
        )
        for appt in appointments:
            exists = db.execute(
                select(ReminderExecution.id).where(
                    ReminderExecution.appointment_id == appt.id,
                    ReminderExecution.kind == "recordatorio_proximo",
                ).limit(1)
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(
                ReminderExecution(
                    appointment_id=appt.id,
                    kind="recordatorio_proximo",
                    status="registrado",
                    detail="Recordatorio automático generado por scheduler (integrar email/SMS según operación).",
                    executed_at=now,
                )
            )
            inserted += 1
        if inserted:
            db.commit()
    return inserted


async def reminder_scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.reminder_scheduler_interval_seconds)
            break
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            break
        try:
            n = run_reminder_batch()
            if n:
                logger.info("Recordatorios registrados: %s", n)
        except Exception:
            logger.exception("Error en scheduler de recordatorios")

