"""Tests for the calendar month helpers."""

from datetime import datetime

import pytest

from voltcast.ingestion.periods import month_bounds, months_between, parse_month


def test_month_bounds_for_a_normal_month() -> None:
    assert month_bounds(2026, 8) == (datetime(2026, 8, 1), datetime(2026, 9, 1))


def test_month_bounds_for_december_moves_to_next_year() -> None:
    assert month_bounds(2026, 12) == (datetime(2026, 12, 1), datetime(2027, 1, 1))


def test_parse_month_reads_year_and_month() -> None:
    assert parse_month("2024-01") == (2024, 1)


def test_parse_month_rejects_other_text() -> None:
    with pytest.raises(ValueError, match="not a month in the form YYYY-MM"):
        parse_month("January 2024")


def test_months_between_includes_both_ends() -> None:
    assert months_between((2026, 5), (2026, 7)) == [(2026, 5), (2026, 6), (2026, 7)]


def test_months_between_crosses_a_year_boundary() -> None:
    assert months_between((2025, 11), (2026, 2)) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]


def test_months_between_for_one_month() -> None:
    assert months_between((2026, 8), (2026, 8)) == [(2026, 8)]


def test_months_between_rejects_a_reversed_range() -> None:
    with pytest.raises(ValueError, match="is after the last month"):
        months_between((2026, 8), (2026, 7))
