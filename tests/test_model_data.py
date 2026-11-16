"""Tests for loading the training table and splitting it by time."""

from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from voltcast.config import Settings
from voltcast.model.columns import FEATURE_COLUMNS
from voltcast.model.data import TABLE_COLUMNS, load_development_table, split_by_time

VALIDATION_START = datetime(2026, 4, 1)
VALIDATION_END = datetime(2026, 4, 3)


def grid(first_issue: str, issues: int) -> pd.DataFrame:
    """Build hourly issue times, each with 48 half-hour targets, and placeholder values."""
    rows = [
        {"issue_time": issue_time, "target_time": issue_time + step * pd.Timedelta(minutes=30)}
        for issue_time in pd.date_range(first_issue, periods=issues, freq="h")
        for step in range(1, 49)
    ]
    table = pd.DataFrame(rows)
    table["actual_price"] = 50.0
    for column in FEATURE_COLUMNS:
        table[column] = 1.0
    return table[TABLE_COLUMNS]


def test_training_answers_are_known_before_validation_starts() -> None:
    training, _ = split_by_time(grid("2026-03-30 00:00", 96), VALIDATION_START, VALIDATION_END)
    assert len(training) > 0
    assert training["target_time"].max() == pd.Timestamp(VALIDATION_START)


def test_validation_forecasts_are_issued_inside_the_period() -> None:
    _, validation = split_by_time(grid("2026-03-30 00:00", 96), VALIDATION_START, VALIDATION_END)
    assert validation["issue_time"].min() == pd.Timestamp(VALIDATION_START)
    assert validation["target_time"].max() == pd.Timestamp(VALIDATION_END)


def test_rows_that_reach_into_the_validation_period_are_in_neither_part() -> None:
    table = grid("2026-03-30 00:00", 96)
    training, validation = split_by_time(table, VALIDATION_START, VALIDATION_END)
    issued_before = table["issue_time"] < VALIDATION_START
    answered_after = table["target_time"] > VALIDATION_START
    dropped_before_validation = int((issued_before & answered_after).sum())
    # Issue times 1 to 23 hours before the start each lose their later targets.
    assert dropped_before_validation == sum(48 - 2 * hours for hours in range(1, 24))
    assert len(training) == int((table["target_time"] <= VALIDATION_START).sum())
    assert len(training) + len(validation) < len(table)


def test_no_forecast_is_in_both_parts() -> None:
    training, validation = split_by_time(
        grid("2026-03-30 00:00", 96), VALIDATION_START, VALIDATION_END
    )
    merged = training.merge(validation, on=["issue_time", "target_time"], how="inner")
    assert len(merged) == 0


def test_reversed_period_is_rejected() -> None:
    with pytest.raises(ValueError, match="validation_start must be before validation_end"):
        split_by_time(grid("2026-03-30 00:00", 2), VALIDATION_END, VALIDATION_START)


def test_load_never_returns_holdout_rows(tmp_path: Path) -> None:
    table = grid("2026-06-29 00:00", 96)  # runs across the holdout start on 1 July 2026
    with duckdb.connect(str(tmp_path / "voltcast.duckdb")) as connection:
        connection.register("table_view", table)
        connection.execute("create table features as select * from table_view")
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert settings.holdout_start == date(2026, 7, 1)

    loaded = load_development_table(settings)

    assert list(loaded.columns) == TABLE_COLUMNS
    assert 0 < len(loaded) < len(table)
    assert loaded["target_time"].max() == pd.Timestamp("2026-07-01 00:00")
