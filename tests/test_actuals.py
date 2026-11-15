"""Tests for the actual prices and demand transform and checks."""

from datetime import datetime

import pandas as pd
import pytest

from voltcast.ingestion.actuals import (
    ACTUALS_COLUMNS,
    find_problems,
    tidy_actuals,
    validate_actuals,
)
from voltcast.ingestion.quality import DataQualityError

START = datetime(2026, 8, 1, 0, 0)
END = datetime(2026, 8, 1, 0, 15)  # three 5-minute intervals: 00:05, 00:10, 00:15
TIMES = pd.date_range("2026-08-01 00:05", periods=3, freq="5min")


def aemo_table(value_column: str, values: list[float], region: str = "VIC1") -> pd.DataFrame:
    """Build a small table in the shape that AEMO provides."""
    return pd.DataFrame(
        {
            "SETTLEMENTDATE": TIMES[: len(values)],
            "REGIONID": region,
            "INTERVENTION": 0,
            value_column: values,
        }
    )


def good_frame() -> pd.DataFrame:
    prices = aemo_table("RRP", [90.0, -20.0, 120.0])
    demand = aemo_table("TOTALDEMAND", [5000.0, 5100.0, 5200.0])
    return tidy_actuals(prices, demand, "VIC1")


def test_tidy_actuals_joins_and_renames() -> None:
    frame = good_frame()
    assert list(frame.columns) == ACTUALS_COLUMNS
    assert len(frame) == 3
    assert frame["price"].tolist() == [90.0, -20.0, 120.0]
    assert frame["demand"].tolist() == [5000.0, 5100.0, 5200.0]


def test_tidy_actuals_drops_other_regions_and_intervention_runs() -> None:
    prices = pd.concat(
        [
            aemo_table("RRP", [90.0, -20.0, 120.0]),
            aemo_table("RRP", [1.0, 2.0, 3.0], region="NSW1"),
            aemo_table("RRP", [7.0, 8.0, 9.0]).assign(INTERVENTION=1),
        ]
    )
    demand = aemo_table("TOTALDEMAND", [5000.0, 5100.0, 5200.0])
    frame = tidy_actuals(prices, demand, "VIC1")
    assert frame["price"].tolist() == [90.0, -20.0, 120.0]


def test_good_data_has_no_problems() -> None:
    assert find_problems(good_frame(), START, END) == []
    validate_actuals(good_frame(), START, END)


def test_missing_interval_is_reported() -> None:
    frame = good_frame().drop(index=1)
    problems = find_problems(frame, START, END)
    assert problems == ["1 missing intervals, first is 2026-08-01 00:10:00"]


def test_duplicate_interval_is_reported() -> None:
    frame = pd.concat([good_frame(), good_frame().iloc[[0]]])
    assert "1 duplicate interval_end values" in find_problems(frame, START, END)


def test_row_missing_from_demand_table_is_reported() -> None:
    prices = aemo_table("RRP", [90.0, -20.0, 120.0])
    demand = aemo_table("TOTALDEMAND", [5000.0, 5100.0])
    frame = tidy_actuals(prices, demand, "VIC1")
    assert len(frame) == 3
    assert "1 empty values in demand" in find_problems(frame, START, END)


def test_price_below_market_floor_is_reported() -> None:
    frame = good_frame()
    frame.loc[0, "price"] = -1500.0
    problems = find_problems(frame, START, END)
    assert problems == ["1 prices below the market floor of -1000.0"]


def test_validate_raises_with_every_problem_listed() -> None:
    frame = good_frame().drop(index=1)
    frame.loc[0, "demand"] = 0.0
    with pytest.raises(DataQualityError) as error:
        validate_actuals(frame, START, END)
    message = str(error.value)
    assert "missing intervals" in message
    assert "zero or negative" in message
