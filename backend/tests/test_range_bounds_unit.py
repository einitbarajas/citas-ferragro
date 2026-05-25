from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.range_bounds import (
    business_local_range_bounds,
    current_month_week_period,
    list_month_week_bounds,
    month_biweekly_bounds,
)


def test_biweekly_period_1_and_2_may_2026():
    tz = ZoneInfo("America/Bogota")
    ref = datetime(2026, 5, 25, 12, 0, tzinfo=tz)

    start1, end1 = business_local_range_bounds("biweekly", ref, tz, period=1)
    assert start1.day == 1
    assert end1.day == 16

    start2, end2 = business_local_range_bounds("biweekly", ref, tz, period=2)
    assert start2.day == 16
    assert end2.month == 6
    assert end2.day == 1


def test_week_period_5_contains_may_25():
    tz = ZoneInfo("America/Bogota")
    ref = datetime(2026, 5, 25, 12, 0, tzinfo=tz)

    start, end = business_local_range_bounds("week", ref, tz, period=5)
    assert start.date().isoformat() == "2026-05-25"
    assert end.date().isoformat() == "2026-06-01"


def test_current_month_week_period_on_may_25():
    tz = ZoneInfo("America/Bogota")
    ref = datetime(2026, 5, 25, 12, 0, tzinfo=tz)
    assert current_month_week_period(ref, tz) == 5


def test_list_month_week_bounds_may_2026_has_five_weeks():
    tz = ZoneInfo("America/Bogota")
    weeks = list_month_week_bounds(2026, 5, tz)
    assert len(weeks) == 5


def test_month_biweekly_bounds_explicit():
    tz = ZoneInfo("America/Bogota")
    start, end = month_biweekly_bounds(2026, 5, 1, tz)
    assert start.day == 1
    assert end.day == 16
