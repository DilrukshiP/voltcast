"""Small helpers for working with calendar months."""

from datetime import datetime


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Return midnight on the first day of the month and of the next month."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def parse_month(text: str) -> tuple[int, int]:
    """Turn text such as '2024-01' into (2024, 1)."""
    try:
        parsed = datetime.strptime(text, "%Y-%m")
    except ValueError as error:
        raise ValueError(f"'{text}' is not a month in the form YYYY-MM") from error
    return parsed.year, parsed.month


def months_between(first: tuple[int, int], last: tuple[int, int]) -> list[tuple[int, int]]:
    """Return every (year, month) from `first` to `last`, including both."""
    if first > last:
        raise ValueError(f"the first month {first} is after the last month {last}")
    months: list[tuple[int, int]] = []
    year, month = first
    while (year, month) <= last:
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months
