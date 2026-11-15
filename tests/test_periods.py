"""Tests for the calendar month helpers."""

from datetime import datetime

from voltcast.ingestion.periods import month_bounds


def test_month_bounds_for_a_normal_month() -> None:
    assert month_bounds(2026, 8) == (datetime(2026, 8, 1), datetime(2026, 9, 1))


def test_month_bounds_for_december_moves_to_next_year() -> None:
    assert month_bounds(2026, 12) == (datetime(2026, 12, 1), datetime(2027, 1, 1))
