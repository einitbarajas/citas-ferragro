from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment_date_window import AppointmentDateWindow
from app.models.appointment_window import AppointmentWindow

SLOT_MINUTES = 90


def list_date_windows_ordered(db: Session, day: date) -> list[AppointmentDateWindow]:
    return (
        db.execute(
            select(AppointmentDateWindow)
            .where(AppointmentDateWindow.day == day)
            .order_by(AppointmentDateWindow.sort_order, AppointmentDateWindow.id)
        )
        .scalars()
        .all()
    )


def list_windows_ordered(db: Session) -> list[AppointmentWindow]:
    return (
        db.execute(select(AppointmentWindow).order_by(AppointmentWindow.sort_order, AppointmentWindow.id))
        .scalars()
        .all()
    )


def format_windows_hint(windows: list[AppointmentWindow]) -> str:
    return format_schedule_hint(windows)


def format_schedule_hint(windows: list[AppointmentWindow]) -> str:
    if not windows:
        return "Sin franjas configuradas."
    parts = []
    for w in windows:
        parts.append(f"{w.start_local.strftime('%H:%M')}–{w.end_local.strftime('%H:%M')}")
    return (
        "Inicio de cita solo entre: "
        + ", ".join(parts)
        + f". Turnos cada {SLOT_MINUTES} minutos (ej.: 08:00, 09:30, 11:00) "
        + f"(hora local {settings.business_timezone})."
    )


def start_time_allowed(db: Session, start: datetime) -> bool:
    tz = ZoneInfo(settings.business_timezone)
    aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    local_dt = aware.astimezone(tz)
    date_windows = list_date_windows_ordered(db, local_dt.date())
    if date_windows:
        windows_for_eval = date_windows
    else:
        windows_for_eval = list_windows_ordered(db)
    if not windows_for_eval:
        return True
    t = local_dt.time()
    for w in windows_for_eval:
        if not (w.start_local <= t <= w.end_local):
            continue
        window_start_minutes = w.start_local.hour * 60 + w.start_local.minute
        t_minutes = t.hour * 60 + t.minute
        if (t_minutes - window_start_minutes) % SLOT_MINUTES == 0:
            return True
    return False


def assert_start_within_windows(db: Session, start: datetime) -> None:
    if not start_time_allowed(db, start):
        tz = ZoneInfo(settings.business_timezone)
        aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        local_dt = aware.astimezone(tz)
        date_windows = list_date_windows_ordered(db, local_dt.date())
        windows = date_windows or list_windows_ordered(db)
        raise HTTPException(
            status_code=400,
            detail=(
                "La hora de inicio no está permitida. "
                + format_schedule_hint(windows)
            ),
        )


def replace_windows(db: Session, items: list[tuple[time, time]]) -> list[AppointmentWindow]:
    db.execute(delete(AppointmentWindow))
    db.flush()
    for idx, (hi, hf) in enumerate(items):
        db.add(AppointmentWindow(start_local=hi, end_local=hf, sort_order=idx))
    db.commit()
    return list_windows_ordered(db)


def replace_date_windows(db: Session, day: date, items: list[tuple[time, time]]) -> list[AppointmentDateWindow]:
    db.execute(delete(AppointmentDateWindow).where(AppointmentDateWindow.day == day))
    db.flush()
    for idx, (hi, hf) in enumerate(items):
        db.add(AppointmentDateWindow(day=day, start_local=hi, end_local=hf, sort_order=idx))
    db.commit()
    return list_date_windows_ordered(db, day)


def clear_date_windows(db: Session, day: date) -> None:
    db.execute(delete(AppointmentDateWindow).where(AppointmentDateWindow.day == day))
    db.commit()
