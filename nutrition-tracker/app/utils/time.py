from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_today_start() -> datetime:
    now = now_utc()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
