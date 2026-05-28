import time
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.provider import Provider

_finalize_last_run_monotonic: float | None = None
FINALIZE_INTERVAL_SECONDS = 60


def enforce_minimum_notice(start_time: datetime, minimum_hours: int = 24):
    now = datetime.now(timezone.utc)
    minimum = now + timedelta(hours=minimum_hours)
    if start_time < minimum:
        raise HTTPException(
            status_code=400,
            detail=f"La cita debe solicitarse con al menos {minimum_hours} horas de anticipación",
        )


def _clamp_unload_teams(value: int | None) -> int:
    cap = max(1, int(getattr(settings, "max_unload_teams", 20)))
    if value is None:
        return 1
    return max(1, min(int(value), cap))


def get_provider_unload_capacity(db: Session, provider_id: int) -> int:
    provider = db.get(Provider, provider_id)
    if provider is None:
        return 1
    return _clamp_unload_teams(provider.unload_teams)


def assert_provider_team_index(provider_id: int, provider_team_index: int, capacity: int) -> None:
    del provider_id, capacity
    if provider_team_index < 1:
        raise HTTPException(status_code=400, detail="Índice de equipo del proveedor inválido.")


def count_schedule_overlaps(
    appointments: Iterable[Appointment],
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> int:
    end_time = start_time + timedelta(minutes=duration_minutes)
    total = 0
    for appt in appointments:
        if exclude_appointment_id is not None and appt.id == exclude_appointment_id:
            continue
        appt_end = appt.start_time + timedelta(minutes=appt.duration_minutes)
        if start_time < appt_end and end_time > appt.start_time:
            total += 1
    return total


def _overlapping_appointments_query(
    *,
    start_time: datetime,
    duration_minutes: int,
    warehouse_unload_team_id: int | None = None,
    provider_id: int | None = None,
    provider_team_index: int | None = None,
    exclude_appointment_id: int | None = None,
):
    end_time = start_time + timedelta(minutes=duration_minutes)
    window_start = start_time - timedelta(hours=12)
    stmt = select(Appointment).where(
        # Para cálculos operativos (reserva/extensión), las citas cerradas
        # no deberían bloquear el uso del horario.
        Appointment.status.not_in(
            [
                AppointmentStatus.cancelado,
                AppointmentStatus.finalizada,
                AppointmentStatus.no_presentada,
            ]
        ),
        Appointment.start_time < end_time,
        Appointment.start_time >= window_start,
    )
    if warehouse_unload_team_id is not None:
        stmt = stmt.where(Appointment.warehouse_unload_team_id == warehouse_unload_team_id)
    if provider_id is not None:
        stmt = stmt.where(Appointment.provider_id == provider_id)
    if provider_team_index is not None:
        stmt = stmt.where(Appointment.provider_team_index == provider_team_index)
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    return stmt


def unload_team_slot_available(
    db: Session,
    warehouse_unload_team_id: int,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> bool:
    rows = db.execute(
        _overlapping_appointments_query(
            start_time=start_time,
            duration_minutes=duration_minutes,
            warehouse_unload_team_id=warehouse_unload_team_id,
            exclude_appointment_id=exclude_appointment_id,
        )
    ).scalars()
    return count_schedule_overlaps(rows, start_time, duration_minutes) < 1


def provider_capacity_available(
    db: Session,
    provider_id: int,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> bool:
    """Sin límite global por proveedor; la bodega limita por muelle/equipo de descarga."""
    del db, provider_id, start_time, duration_minutes, exclude_appointment_id
    return True


def assert_unload_team_slot(
    db: Session,
    warehouse_unload_team_id: int,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> None:
    if unload_team_slot_available(
        db, warehouse_unload_team_id, start_time, duration_minutes, exclude_appointment_id
    ):
        return
    raise HTTPException(
        status_code=409,
        detail="Ese equipo de descarga ya tiene una cita en ese horario. Elige otro turno u otro equipo.",
    )


def assert_provider_capacity(
    db: Session,
    provider_id: int,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> None:
    del db, provider_id, start_time, duration_minutes, exclude_appointment_id


def provider_schedule_conflicts(
    db: Session,
    provider_id: int,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> bool:
    return not provider_capacity_available(
        db, provider_id, start_time, duration_minutes, exclude_appointment_id
    )


def assert_provider_no_schedule_overlap(
    db: Session,
    provider_id: int,
    start_time: datetime,
    duration_minutes: int,
    exclude_appointment_id: int | None = None,
) -> None:
    assert_provider_capacity(
        db, provider_id, start_time, duration_minutes, exclude_appointment_id
    )


def can_extend_without_overlap(db: Session, appointment: Appointment, extra_minutes: int) -> bool:
    new_duration = appointment.duration_minutes + extra_minutes
    return unload_team_slot_available(
        db,
        appointment.warehouse_unload_team_id,
        appointment.start_time,
        new_duration,
        exclude_appointment_id=appointment.id,
    )


def slot_conflict_check(
    db: Session,
    start_time: datetime,
    duration_minutes: int,
    warehouse_unload_team_id: int,
    exclude_appointment_id: int | None = None,
    provider_id: int | None = None,
) -> bool:
    if not unload_team_slot_available(
        db, warehouse_unload_team_id, start_time, duration_minutes, exclude_appointment_id
    ):
        return True
    if provider_id is not None and not provider_capacity_available(
        db, provider_id, start_time, duration_minutes, exclude_appointment_id
    ):
        return True
    return False


def reserve_slot_fifo_or_raise(
    db: Session,
    start_time: datetime,
    duration_minutes: int,
    warehouse_unload_team_id: int,
    exclude_appointment_id: int | None = None,
    provider_id: int | None = None,
) -> None:
    lock_key = int(warehouse_unload_team_id) * 1_000_000_000 + int(start_time.timestamp() // 60)
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
    assert_unload_team_slot(
        db, warehouse_unload_team_id, start_time, duration_minutes, exclude_appointment_id
    )
    if provider_id is not None:
        assert_provider_capacity(
            db, provider_id, start_time, duration_minutes, exclude_appointment_id
        )


# Compatibilidad temporal con llamadas que aún pasan warehouse_id.
def warehouse_capacity_available(*_args, **_kwargs) -> bool:
    return True


def get_warehouse_unload_capacity(db: Session, warehouse_id: int) -> int:
    from app.services.unload_teams import list_active_unload_teams

    return len(list_active_unload_teams(db, warehouse_id))


def finalize_elapsed_appointments(db: Session) -> int:
    global _finalize_last_run_monotonic
    tick = time.monotonic()
    if _finalize_last_run_monotonic is not None and tick - _finalize_last_run_monotonic < FINALIZE_INTERVAL_SECONDS:
        return 0
    _finalize_last_run_monotonic = tick

    now = datetime.now(timezone.utc)
    # Solo sin_revision: revisado queda en ventana de 15 min para marcar finalizada/no presentada.
    candidates = (
        db.execute(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.sin_revision,
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
