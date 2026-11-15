"""Small helpers for working with calendar months."""

from datetime import datetime


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Return midnight on the first day of the month and of the next month."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end
