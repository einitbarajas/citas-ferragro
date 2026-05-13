from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus


def enforce_minimum_notice(start_time: datetime, minimum_hours: int = 24):
    now = datetime.now(timezone.utc)
    minimum = now + timedelta(hours=minimum_hours)
    if start_time < minimum:
        raise HTTPException(
            status_code=400,
            detail=f"La cita debe solicitarse con al menos {minimum_hours} horas de anticipación",
        )


def can_extend_without_overlap(db: Session, appointment: Appointment, extra_minutes: int) -> bool:
    current_end = appointment.start_time + timedelta(minutes=appointment.duration_minutes)
    new_end = current_end + timedelta(minutes=extra_minutes)
    stmt = (
        select(Appointment)
        .where(Appointment.start_time >= current_end, Appointment.id != appointment.id)
        .order_by(Appointment.start_time.asc())
        .limit(1)
    )
    next_appointment = db.execute(stmt).scalar_one_or_none()
    if not next_appointment:
        return True
    return next_appointment.start_time >= new_end


def slot_conflict_check(
    db: Session,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> bool:
    """Devuelve True si el intervalo choca con otra cita (no cancelada)."""
    try:
        reserve_slot_fifo_or_raise(db, start_time, duration_minutes, exclude_appointment_id)
        return False
    except HTTPException as exc:
        if exc.status_code == 409:
            return True
        raise


def reserve_slot_fifo_or_raise(
    db: Session,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> None:
    """
    Asegura FIFO por franja usando lock transaccional:
    el primero en adquirir el lock y confirmar se queda con la cita.
    """
    lock_key = int(start_time.timestamp() // 60)
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
    end_time = start_time + timedelta(minutes=duration_minutes)
    stmt = select(Appointment).where(Appointment.status != AppointmentStatus.cancelado)
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    appointments = db.execute(stmt).scalars()
    for appt in appointments:
        appt_end = appt.start_time + timedelta(minutes=appt.duration_minutes)
        if start_time < appt_end and end_time > appt.start_time:
            raise HTTPException(
                status_code=409,
                detail="Conflicto de horario con otra cita. Para agendar, debes cambiar el horario.",
            )


def finalize_elapsed_appointments(db: Session) -> int:
    """
    Marca como finalizadas las citas abiertas cuya fecha/hora de inicio ya pasó.
    """
    now = datetime.now(timezone.utc)
    candidates = (
        db.execute(
            select(Appointment).where(
                Appointment.status.in_([AppointmentStatus.sin_revision, AppointmentStatus.revisado]),
                Appointment.start_time <= now,
            )
        )
        .scalars()
        .all()
    )
    updated = 0
    for appt in candidates:
        if appt.start_time <= now:
            appt.status = AppointmentStatus.finalizada
            updated += 1
    if updated > 0:
        db.commit()
    return updated
