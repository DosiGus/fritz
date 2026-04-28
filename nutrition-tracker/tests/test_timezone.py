from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.utils.time import user_day_bounds_utc, user_today, user_zone


def test_user_day_bounds_utc_los_angeles_dst():
    start, end = user_day_bounds_utc(date(2026, 4, 15), "America/Los_Angeles")
    assert start == datetime(2026, 4, 15, 7, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 4, 16, 7, 0, tzinfo=timezone.utc)


def test_user_zone_handles_invalid_tz():
    assert user_zone("Not/A/Real_Zone") == ZoneInfo("UTC")
    assert user_today("garbage") == datetime.now(timezone.utc).date()


def test_user_day_bounds_utc_berlin_spring_forward():
    start, end = user_day_bounds_utc(date(2026, 3, 29), "Europe/Berlin")
    assert start == datetime(2026, 3, 28, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 3, 29, 22, 0, tzinfo=timezone.utc)
