from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_today_start() -> datetime:
    now = now_utc()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def user_zone(tz_name: str | None) -> ZoneInfo:
    if not tz_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def user_today(tz_name: str | None) -> date:
    return datetime.now(user_zone(tz_name)).date()


def user_day_bounds_utc(day: date, tz_name: str | None) -> tuple[datetime, datetime]:
    """Return [start, end_exclusive) UTC datetimes spanning the given local day."""
    zone = user_zone(tz_name)
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
