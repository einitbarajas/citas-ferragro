from datetime import date, datetime, time, timedelta, timezone
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
# Duración típica para turnos consecutivos dentro de una franja larga (ej. 10:01–11:01 y 11:01–12:00).
CONSECUTIVE_BOOKING_MINUTES = 60


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(total_minutes: int) -> time:
    total_minutes = max(0, min(total_minutes, 23 * 60 + 59))
    return time(total_minutes // 60, total_minutes % 60)


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


def get_team_scheduled_iso_weekdays(
    db: Session, warehouse_id: int, warehouse_unload_team_id: int
) -> set[int]:
    """Días ISO (1=lun..7=dom) presentes en franjas por fecha futuras del equipo."""
    tz = ZoneInfo(settings.business_timezone)
    local_today = datetime.now(tz).date()
    rows = (
        db.execute(
            select(AppointmentDateWindow.day)
            .where(
                AppointmentDateWindow.warehouse_id == warehouse_id,
                AppointmentDateWindow.warehouse_unload_team_id == warehouse_unload_team_id,
                AppointmentDateWindow.day >= local_today,
            )
            .distinct()
        )
        .scalars()
        .all()
    )
    return {d.isoweekday() for d in rows}


def resolve_team_windows_for_day(
    db: Session, day: date, warehouse_id: int, warehouse_unload_team_id: int | None
) -> tuple[list, str]:
    """Franjas efectivas del día: excepción por fecha, o semanal con tope por días ya configurados."""
    date_windows = list_date_windows_ordered(db, day, warehouse_id, warehouse_unload_team_id)
    if date_windows:
        return date_windows, "date_override"
    weekly = list_windows_ordered(db, warehouse_id, warehouse_unload_team_id)
    if not weekly:
        return [], "none"
    if warehouse_unload_team_id is not None:
        scheduled_weekdays = get_team_scheduled_iso_weekdays(db, warehouse_id, warehouse_unload_team_id)
        if scheduled_weekdays and day.isoweekday() not in scheduled_weekdays:
            return [], "none"
    return weekly, "weekly"


def day_has_team_schedule(
    db: Session, day: date, warehouse_id: int, warehouse_unload_team_id: int
) -> bool:
    windows, _ = resolve_team_windows_for_day(db, day, warehouse_id, warehouse_unload_team_id)
    return bool(windows)


def list_warehouse_open_days_in_month(db: Session, year: int, month: int, warehouse_id: int) -> list[str]:
    from app.services.unload_teams import list_active_unload_teams

    teams = list_active_unload_teams(db, warehouse_id)
    if not teams:
        return []
    start_day = date(year, month, 1)
    if month == 12:
        end_day = date(year + 1, 1, 1)
    else:
        end_day = date(year, month + 1, 1)
    open_days: list[str] = []
    cursor = start_day
    while cursor < end_day:
        for team in teams:
            if day_has_team_schedule(db, cursor, warehouse_id, team.id):
                open_days.append(str(cursor))
                break
        cursor += timedelta(days=1)
    return open_days


def list_team_open_days_in_month(
    db: Session, year: int, month: int, warehouse_id: int, warehouse_unload_team_id: int
) -> list[str]:
    """Días del mes en los que el equipo tiene franja (semanal y/o excepción por fecha)."""
    start_day = date(year, month, 1)
    if month == 12:
        end_day = date(year + 1, 1, 1)
    else:
        end_day = date(year, month + 1, 1)
    open_days: list[str] = []
    cursor = start_day
    while cursor < end_day:
        if day_has_team_schedule(db, cursor, warehouse_id, warehouse_unload_team_id):
            open_days.append(str(cursor))
        cursor += timedelta(days=1)
    return open_days


def get_active_warehouse_or_raise(db: Session, warehouse_id: int) -> Warehouse:
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise HTTPException(status_code=400, detail="La bodega no existe o no está activa.")
    return warehouse


def list_date_windows_ordered(
    db: Session,
    day: date,
    warehouse_id: int,
    warehouse_unload_team_id: int | None = None,
) -> list[AppointmentDateWindow]:
    if warehouse_unload_team_id is not None:
        team_rows = (
            db.execute(
                select(AppointmentDateWindow)
                .where(
                    AppointmentDateWindow.day == day,
                    AppointmentDateWindow.warehouse_id == warehouse_id,
                    AppointmentDateWindow.warehouse_unload_team_id == warehouse_unload_team_id,
                )
                .order_by(AppointmentDateWindow.sort_order, AppointmentDateWindow.id)
            )
            .scalars()
            .all()
        )
        return team_rows
    return (
        db.execute(
            select(AppointmentDateWindow)
            .where(
                AppointmentDateWindow.day == day,
                AppointmentDateWindow.warehouse_id == warehouse_id,
                AppointmentDateWindow.warehouse_unload_team_id.is_(None),
            )
            .order_by(AppointmentDateWindow.sort_order, AppointmentDateWindow.id)
        )
        .scalars()
        .all()
    )


def list_windows_ordered(
    db: Session, warehouse_id: int, warehouse_unload_team_id: int | None = None
) -> list[AppointmentWindow]:
    if warehouse_unload_team_id is not None:
        team_rows = (
            db.execute(
                select(AppointmentWindow)
                .where(
                    AppointmentWindow.warehouse_id == warehouse_id,
                    AppointmentWindow.warehouse_unload_team_id == warehouse_unload_team_id,
                )
                .order_by(AppointmentWindow.sort_order, AppointmentWindow.id)
            )
            .scalars()
            .all()
        )
        return team_rows
    return (
        db.execute(
            select(AppointmentWindow)
            .where(
                AppointmentWindow.warehouse_id == warehouse_id,
                AppointmentWindow.warehouse_unload_team_id.is_(None),
            )
            .order_by(AppointmentWindow.sort_order, AppointmentWindow.id)
        )
        .scalars()
        .all()
    )


def iter_bookable_slots(windows: list) -> list[tuple[time, time, int]]:
    """Turnos agendables: franja completa y, si es larga, bloques consecutivos (p. ej. 60 min)."""
    seen: set[tuple[str, str, int]] = set()
    out: list[tuple[time, time, int]] = []

    def add_slot(slot_start: time, slot_end: time, minutes: int) -> None:
        if minutes < MIN_SLOT_MINUTES or minutes > MAX_SLOT_MINUTES:
            return
        key = (slot_start.strftime("%H:%M"), slot_end.strftime("%H:%M"), minutes)
        if key in seen:
            return
        seen.add(key)
        out.append((slot_start, slot_end, minutes))

    for w in windows:
        duration = slot_duration_minutes(w.start_local, w.end_local)
        if duration < MIN_SLOT_MINUTES or duration > MAX_SLOT_MINUTES:
            continue
        add_slot(w.start_local, w.end_local, duration)
        if duration > CONSECUTIVE_BOOKING_MINUTES:
            cursor = _time_to_minutes(w.start_local)
            end_bound = _time_to_minutes(w.end_local)
            while cursor + CONSECUTIVE_BOOKING_MINUTES <= end_bound:
                block_end = cursor + CONSECUTIVE_BOOKING_MINUTES
                add_slot(_minutes_to_time(cursor), _minutes_to_time(block_end), CONSECUTIVE_BOOKING_MINUTES)
                cursor = block_end
            remainder = end_bound - cursor
            if remainder >= MIN_SLOT_MINUTES:
                add_slot(_minutes_to_time(cursor), w.end_local, remainder)
    out.sort(key=lambda row: (_time_to_minutes(row[0]), row[2]))
    return out


def appointment_fits_in_windows(
    start_local: time, duration_minutes: int, windows: list
) -> bool:
    """La cita cabe dentro de alguna franja configurada (sin exigir coincidencia exacta de turno)."""
    if duration_minutes < MIN_SLOT_MINUTES or duration_minutes > MAX_SLOT_MINUTES:
        return False
    start_m = _time_to_minutes(start_local)
    end_m = start_m + duration_minutes
    for w in windows:
        w_start = _time_to_minutes(w.start_local)
        w_end = _time_to_minutes(w.end_local)
        if start_m >= w_start and end_m <= w_end:
            return True
    return False


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
    warehouse_unload_team_id: int | None = None,
) -> bool:
    tz = ZoneInfo(settings.business_timezone)
    aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    local_dt = aware.astimezone(tz)
    windows_for_eval, _ = resolve_team_windows_for_day(
        db, local_dt.date(), warehouse_id, warehouse_unload_team_id
    )
    if not windows_for_eval:
        return False
    t = local_dt.time()
    for slot_start, slot_end, expected_duration in iter_bookable_slots(windows_for_eval):
        if appointment_matches_slot(t, duration_minutes, slot_start, slot_end):
            return True
    return False


def assert_appointment_fits_windows(
    db: Session,
    start: datetime,
    duration_minutes: int,
    warehouse_id: int,
    warehouse_unload_team_id: int | None = None,
) -> None:
    tz = ZoneInfo(settings.business_timezone)
    aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    local_dt = aware.astimezone(tz)
    windows, _ = resolve_team_windows_for_day(
        db, local_dt.date(), warehouse_id, warehouse_unload_team_id
    )
    if not appointment_fits_in_windows(local_dt.time(), duration_minutes, windows):
        raise HTTPException(
            status_code=400,
            detail=(
                "La hora y duración deben quedar dentro de una franja habilitada. "
                + format_schedule_hint(windows)
            ),
        )


def assert_appointment_slot(
    db: Session,
    start: datetime,
    duration_minutes: int,
    warehouse_id: int,
    warehouse_unload_team_id: int | None = None,
) -> None:
    if not start_time_allowed(db, start, duration_minutes, warehouse_id, warehouse_unload_team_id):
        tz = ZoneInfo(settings.business_timezone)
        aware = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        local_dt = aware.astimezone(tz)
        windows, _ = resolve_team_windows_for_day(
            db, local_dt.date(), warehouse_id, warehouse_unload_team_id
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "La hora y duración no coinciden con un turno habilitado. "
                + format_schedule_hint(windows)
            ),
        )


def assert_start_within_windows(db: Session, start: datetime, warehouse_id: int, duration_minutes: int) -> None:
    assert_appointment_slot(db, start, duration_minutes, warehouse_id)


def replace_windows(
    db: Session,
    warehouse_id: int,
    items: list[tuple[time, time]],
    warehouse_unload_team_id: int | None = None,
) -> list[AppointmentWindow]:
    stmt = delete(AppointmentWindow).where(AppointmentWindow.warehouse_id == warehouse_id)
    if warehouse_unload_team_id is None:
        stmt = stmt.where(AppointmentWindow.warehouse_unload_team_id.is_(None))
    else:
        stmt = stmt.where(AppointmentWindow.warehouse_unload_team_id == warehouse_unload_team_id)
    db.execute(stmt)
    db.flush()
    for idx, (hi, hf) in enumerate(items):
        _assert_slot_duration_valid(hi, hf, "Franja semanal")
        db.add(
            AppointmentWindow(
                warehouse_id=warehouse_id,
                warehouse_unload_team_id=warehouse_unload_team_id,
                start_local=hi,
                end_local=hf,
                sort_order=idx,
            )
        )
    db.commit()
    return list_windows_ordered(db, warehouse_id, warehouse_unload_team_id)


def replace_date_windows(
    db: Session,
    day: date,
    warehouse_id: int,
    items: list[tuple[time, time]],
    warehouse_unload_team_id: int | None = None,
) -> list[AppointmentDateWindow]:
    stmt = delete(AppointmentDateWindow).where(
        AppointmentDateWindow.day == day,
        AppointmentDateWindow.warehouse_id == warehouse_id,
    )
    if warehouse_unload_team_id is None:
        stmt = stmt.where(AppointmentDateWindow.warehouse_unload_team_id.is_(None))
    else:
        stmt = stmt.where(AppointmentDateWindow.warehouse_unload_team_id == warehouse_unload_team_id)
    db.execute(stmt)
    db.flush()
    for idx, (hi, hf) in enumerate(items):
        _assert_slot_duration_valid(hi, hf, "Franja por fecha")
        db.add(
            AppointmentDateWindow(
                day=day,
                warehouse_id=warehouse_id,
                warehouse_unload_team_id=warehouse_unload_team_id,
                start_local=hi,
                end_local=hf,
                sort_order=idx,
            )
        )
    db.commit()
    return list_date_windows_ordered(db, day, warehouse_id, warehouse_unload_team_id)


def clear_date_windows(
    db: Session,
    day: date,
    warehouse_id: int,
    warehouse_unload_team_id: int | None = None,
) -> None:
    stmt = delete(AppointmentDateWindow).where(
        AppointmentDateWindow.day == day,
        AppointmentDateWindow.warehouse_id == warehouse_id,
    )
    if warehouse_unload_team_id is None:
        stmt = stmt.where(AppointmentDateWindow.warehouse_unload_team_id.is_(None))
    else:
        stmt = stmt.where(AppointmentDateWindow.warehouse_unload_team_id == warehouse_unload_team_id)
    db.execute(stmt)
    db.commit()
