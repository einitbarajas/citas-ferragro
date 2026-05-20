from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment_date_window import AppointmentDateWindow
from app.models.appointment_window import AppointmentWindow
from app.models.warehouse import Warehouse

MIN_SLOT_MINUTES = 15
MAX_SLOT_MINUTES = 480


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def slot_duration_minutes(start_local: time, end_local: time) -> int:
    return _time_to_minutes(end_local) - _time_to_minutes(start_local)


def _assert_slot_duration_valid(start_local: time, end_local: time, error_prefix: str = "Franja") -> int:
    minutes = slot_duration_minutes(start_local, end_local)
    if minutes < MIN_SLOT_MINUTES:
        raise HTTPException(
            status_code=400,
            detail=f"{error_prefix}: la duración mínima de un turno es {MIN_SLOT_MINUTES} minutos.",
        )
    if minutes > MAX_SLOT_MINUTES:
        raise HTTPException(
            status_code=400,
            detail=f"{error_prefix}: la duración máxima de un turno es {MAX_SLOT_MINUTES} minutos.",
        )
    return minutes


def get_active_warehouse_or_raise(db: Session, warehouse_id: int) -> Warehouse:
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise HTTPException(status_code=400, detail="La bodega no existe o no está activa.")
    return warehouse


def list_date_windows_ordered(db: Session, day: date, warehouse_id: int) -> list[AppointmentDateWindow]:
    return (
        db.execute(
            select(AppointmentDateWindow)
            .where(
                AppointmentDateWindow.day == day,
                AppointmentDateWindow.warehouse_id == warehouse_id,
            )
            .order_by(AppointmentDateWindow.sort_order, AppointmentDateWindow.id)
        )
        .scalars()
        .all()
    )


def list_windows_ordered(db: Session, warehouse_id: int) -> list[AppointmentWindow]:
    return (
        db.execute(
            select(AppointmentWindow)
            .where(AppointmentWindow.warehouse_id == warehouse_id)
            .order_by(AppointmentWindow.sort_order, AppointmentWindow.id)
        )
        .scalars()
        .all()
    )


def iter_bookable_slots(windows: list) -> list[tuple[time, time, int]]:
    """Cada fila de franja es un turno agendable (inicio, fin, duración en minutos)."""
    out: list[tuple[time, time, int]] = []
    for w in windows:
        duration = slot_duration_minutes(w.start_local, w.end_local)
        if duration < MIN_SLOT_MINUTES or duration > MAX_SLOT_MINUTES:
            continue
        out.append((w.start_local, w.end_local, duration))
    return out


def format_schedule_hint(windows: list) -> str:
    if not windows:
        return "Sin turnos configurados."
    parts = []
    for w in windows:
        duration = slot_duration_minutes(w.start_local, w.end_local)
        parts.append(
            f"{w.start_local.strftime('%H:%M')}–{w.end_local.strftime('%H:%M')} ({duration} min)"
        )
    return (
        "Turnos agendables: "
        + ", ".join(parts)
        + f" (hora local {settings.business_timezone})."
    )


def format_windows_hint(windows: list) -> str:
    return format_schedule_hint(windows)


def appointment_matches_slot(start_local: time, duration_minutes: int, slot_start: time, slot_end: time) -> bool:
    expected = slot_duration_minutes(slot_start, slot_end)
    return start_local == slot_start and duration_minutes == expected


def start_time_allowed(
    db: Session,
    start: datetime,
    duration_minutes: int,
    warehouse_id: int,
) -> bool:
    tz = ZoneInfo(settings.business_timezone)
    aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    local_dt = aware.astimezone(tz)
    date_windows = list_date_windows_ordered(db, local_dt.date(), warehouse_id)
    windows_for_eval = date_windows or list_windows_ordered(db, warehouse_id)
    if not windows_for_eval:
        return False
    t = local_dt.time()
    for slot_start, slot_end, expected_duration in iter_bookable_slots(windows_for_eval):
        if appointment_matches_slot(t, duration_minutes, slot_start, slot_end):
            return True
    return False


def assert_appointment_slot(
    db: Session,
    start: datetime,
    duration_minutes: int,
    warehouse_id: int,
) -> None:
    if not start_time_allowed(db, start, duration_minutes, warehouse_id):
        tz = ZoneInfo(settings.business_timezone)
        aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        local_dt = aware.astimezone(tz)
        date_windows = list_date_windows_ordered(db, local_dt.date(), warehouse_id)
        windows = date_windows or list_windows_ordered(db, warehouse_id)
        raise HTTPException(
            status_code=400,
            detail=(
                "La hora y duración no coinciden con un turno habilitado. "
                + format_schedule_hint(windows)
            ),
        )


def assert_start_within_windows(db: Session, start: datetime, warehouse_id: int, duration_minutes: int) -> None:
    assert_appointment_slot(db, start, duration_minutes, warehouse_id)


def replace_windows(db: Session, warehouse_id: int, items: list[tuple[time, time]]) -> list[AppointmentWindow]:
    db.execute(delete(AppointmentWindow).where(AppointmentWindow.warehouse_id == warehouse_id))
    db.flush()
    for idx, (hi, hf) in enumerate(items):
        _assert_slot_duration_valid(hi, hf, "Franja semanal")
        db.add(
            AppointmentWindow(
                warehouse_id=warehouse_id,
                start_local=hi,
                end_local=hf,
                sort_order=idx,
            )
        )
    db.commit()
    return list_windows_ordered(db, warehouse_id)


def replace_date_windows(
    db: Session, day: date, warehouse_id: int, items: list[tuple[time, time]]
) -> list[AppointmentDateWindow]:
    db.execute(
        delete(AppointmentDateWindow).where(
            AppointmentDateWindow.day == day,
            AppointmentDateWindow.warehouse_id == warehouse_id,
        )
    )
    db.flush()
    for idx, (hi, hf) in enumerate(items):
        _assert_slot_duration_valid(hi, hf, "Franja por fecha")
        db.add(
            AppointmentDateWindow(
                day=day,
                warehouse_id=warehouse_id,
                start_local=hi,
                end_local=hf,
                sort_order=idx,
            )
        )
    db.commit()
    return list_date_windows_ordered(db, day, warehouse_id)


def clear_date_windows(db: Session, day: date, warehouse_id: int) -> None:
    db.execute(
        delete(AppointmentDateWindow).where(
            AppointmentDateWindow.day == day,
            AppointmentDateWindow.warehouse_id == warehouse_id,
        )
    )
    db.commit()
