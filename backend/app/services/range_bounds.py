from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func

DAY_NAMES_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


def appointment_local_date_sql(column, tz_name: str):
    """Fecha calendario en zona horaria de negocio (PostgreSQL timestamptz)."""
    return cast(func.timezone(tz_name, column), Date)


def _month_end_date(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def month_biweekly_bounds(
    year: int,
    month: int,
    period: int,
    tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    if period == 1:
        start = datetime(year, month, 1, tzinfo=tz)
        end = datetime(year, month, 16, tzinfo=tz)
        return start, end
    start = datetime(year, month, 16, tzinfo=tz)
    month_end = _month_end_date(year, month)
    end = datetime(month_end.year, month_end.month, month_end.day, tzinfo=tz)
    return start, end


def list_month_week_bounds(
    year: int,
    month: int,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    month_start = date(year, month, 1)
    month_end = _month_end_date(year, month)
    monday = month_start - timedelta(days=month_start.weekday())
    weeks: list[tuple[datetime, datetime]] = []
    while monday < month_end:
        week_end = monday + timedelta(days=7)
        if week_end > month_start and monday < month_end:
            weeks.append(
                (
                    datetime(monday.year, monday.month, monday.day, tzinfo=tz),
                    datetime(week_end.year, week_end.month, week_end.day, tzinfo=tz),
                )
            )
        monday += timedelta(days=7)
    return weeks


def month_week_bounds(
    year: int,
    month: int,
    period: int,
    tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    weeks = list_month_week_bounds(year, month, tz)
    if not weeks:
        local_today = datetime(year, month, 1, tzinfo=tz)
        return business_local_range_bounds("week", local_today, tz)
    index = max(1, min(period, len(weeks))) - 1
    return weeks[index]


def current_month_week_period(local_now: datetime, tz: ZoneInfo) -> int:
    weeks = list_month_week_bounds(local_now.year, local_now.month, tz)
    today = local_now.date()
    for index, (start, end) in enumerate(weeks, start=1):
        if start.date() <= today < end.date():
            return index
    return len(weeks) or 1


def business_local_range_bounds(
    range_mode: str,
    local_now: datetime,
    tz: ZoneInfo,
    period: int | None = None,
) -> tuple[datetime, datetime]:
    local_today_start = datetime(local_now.year, local_now.month, local_now.day, tzinfo=tz)

    if range_mode == "month":
        local_range_start = datetime(local_now.year, local_now.month, 1, tzinfo=tz)
        if local_now.month == 12:
            local_range_end = datetime(local_now.year + 1, 1, 1, tzinfo=tz)
        else:
            local_range_end = datetime(local_now.year, local_now.month + 1, 1, tzinfo=tz)
        return local_range_start, local_range_end

    if range_mode == "week":
        if period is not None:
            return month_week_bounds(local_now.year, local_now.month, period, tz)
        monday_offset = local_today_start.weekday()
        local_range_start = local_today_start - timedelta(days=monday_offset)
        local_range_end = local_range_start + timedelta(days=7)
        return local_range_start, local_range_end

    if range_mode == "biweekly":
        if period is not None:
            return month_biweekly_bounds(local_now.year, local_now.month, period, tz)
        if local_now.day <= 15:
            local_range_start = datetime(local_now.year, local_now.month, 1, tzinfo=tz)
            local_range_end = datetime(local_now.year, local_now.month, 16, tzinfo=tz)
        else:
            local_range_start = datetime(local_now.year, local_now.month, 16, tzinfo=tz)
            if local_now.month == 12:
                local_range_end = datetime(local_now.year + 1, 1, 1, tzinfo=tz)
            else:
                local_range_end = datetime(local_now.year, local_now.month + 1, 1, tzinfo=tz)
        return local_range_start, local_range_end

    local_range_start = local_today_start
    local_range_end = local_today_start + timedelta(days=1)
    return local_range_start, local_range_end


def build_daily_counts_in_range(
    range_start: datetime,
    range_end: datetime,
    day_counts: dict[str, int],
) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    current = range_start
    while current < range_end:
        d = current.date()
        iso = str(d)
        rows.append(
            {
                "fecha": iso,
                "dia": DAY_NAMES_ES[current.weekday()],
                "cantidad": day_counts.get(iso, 0),
            }
        )
        current += timedelta(days=1)
    return rows
