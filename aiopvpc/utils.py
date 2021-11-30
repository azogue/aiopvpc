from datetime import datetime

from aiopvpc.const import UTC_TZ


def ensure_utc_time(ts: datetime) -> datetime:
    """Return tz-aware datetime in UTC from any datetime."""
    if ts.tzinfo is None:
        return datetime(*ts.timetuple()[:6], tzinfo=UTC_TZ)
    elif str(ts.tzinfo) != str(UTC_TZ):
        return ts.astimezone(UTC_TZ)
    return ts
