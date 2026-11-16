"""Tests for the committed list of Victorian public holidays."""

import csv
from pathlib import Path

SEED_PATH = Path("dbt/seeds/vic_public_holidays.csv")


def read_seed() -> dict[str, str]:
    with SEED_PATH.open(newline="", encoding="utf-8") as file:
        return {row["holiday_date"]: row["holiday_name"] for row in csv.DictReader(file)}


def test_seed_holds_days_that_only_victoria_has() -> None:
    seed = read_seed()
    assert seed["2024-09-27"] == "Friday before the AFL Grand Final"
    assert seed["2025-11-04"] == "Melbourne Cup Day"
    assert seed["2026-03-09"] == "Labour Day"


def test_seed_holds_national_days() -> None:
    seed = read_seed()
    assert "2024-12-25" in seed
    assert "2025-04-25" in seed
    assert "2026-01-26" in seed


def test_seed_covers_every_year_of_the_history() -> None:
    years = {holiday_date[:4] for holiday_date in read_seed()}
    assert {"2024", "2025", "2026"} <= years


def test_seed_is_sorted_and_has_no_ordinary_day() -> None:
    dates = list(read_seed())
    assert dates == sorted(dates)
    assert "2026-03-10" not in dates
