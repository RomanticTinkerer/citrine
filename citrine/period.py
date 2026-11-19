"""Date ranges for downloads. Write a year, a month or a day: 2020, 2020-05, 2020-05-17."""
import calendar
import datetime as dt
import re


def parse(text, end=False):
    """First day of the period, or the last day when end=True. Raises ValueError with a hint."""
    m = re.fullmatch(r"(\d{4})(?:[-./](\d{1,2})(?:[-./](\d{1,2}))?)?", (text or "").strip())
    if not m:
        raise ValueError(f"bad date {text!r}: use 2020, 2020-05 or 2020-05-17")
    year, month, day = int(m[1]), int(m[2] or (12 if end else 1)), m[3] and int(m[3])
    if not 1 <= month <= 12:
        raise ValueError(f"bad month in {text!r}")
    return dt.date(year, month, day or (calendar.monthrange(year, month)[1] if end else 1))


def parse_range(since=None, until=None):
    """(first day, last day) as dates, either may be None. 'from 2019 to 2021' covers all of both years."""
    a = parse(since) if since else None
    b = parse(until, end=True) if until else None
    if a and b and a > b:
        raise ValueError(f"the start ({since}) is after the end ({until})")
    return a, b


def to_ms(day, end=False):
    """Milliseconds since the epoch (UTC) at the start of `day`, or its last millisecond."""
    t = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    return int((t + dt.timedelta(days=1)).timestamp() * 1000) - 1 if end else int(t.timestamp() * 1000)
