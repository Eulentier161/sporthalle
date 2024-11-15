import re
from datetime import date, datetime, time, timedelta


def parse_datetime(d: date, match: re.Match[str] | None) -> datetime | None:
    if not match:
        return None

    g = match.group(1)
    if type(g) is not str:
        return None

    hour, minute = map(int, g.split(":"))

    return datetime.combine(d, time(hour, minute))


def add_hours_avoiding_next_day(dt: datetime | None, hours: int) -> datetime | None:
    if dt is None:
        return None
    new_dt = dt + timedelta(hours=hours)
    if new_dt.day != dt.day:
        # If the new datetime is on the next day, set it to the end of the current day
        new_dt = datetime.combine(dt.date() + timedelta(days=1), time())
    return new_dt
