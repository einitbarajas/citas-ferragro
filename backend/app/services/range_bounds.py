from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def business_local_range_bounds(
    range_mode: str,
    local_now: datetime,
    tz: ZoneInfo,
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
        monday_offset = local_today_start.weekday()
        local_range_start = local_today_start - timedelta(days=monday_offset)
        local_range_end = local_range_start + timedelta(days=7)
        return local_range_start, local_range_end

    if range_mode == "biweekly":
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
