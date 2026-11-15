"""Actual prices and demand: turn AEMO tables into one clean table and check it.

This module has no network code. It only transforms and validates tables,
so every function can be tested with small hand-made data.
"""

from datetime import datetime

import pandas as pd

from voltcast.ingestion.quality import DataQualityError

INTERVAL: pd.Timedelta = pd.Timedelta(minutes=5)
MARKET_PRICE_FLOOR: float = -1000.0  # dollars per MWh, set by the market rules
ACTUALS_COLUMNS: list[str] = ["region", "interval_end", "price", "demand"]


def _select(frame: pd.DataFrame, region: str, value_column: str) -> pd.DataFrame:
    """Keep one region and the normal market run, and only the columns we need."""
    keep = (frame["REGIONID"] == region) & (frame["INTERVENTION"] == 0)
    return frame.loc[keep, ["REGIONID", "SETTLEMENTDATE", value_column]]


def tidy_actuals(prices: pd.DataFrame, demand: pd.DataFrame, region: str) -> pd.DataFrame:
    """Join AEMO price and demand tables into one table with our column names.

    The join keeps rows that exist in only one table. Their empty values are then
    reported by `validate_actuals`, so a missing row is never dropped silently.
    """
    merged = _select(prices, region, "RRP").merge(
        _select(demand, region, "TOTALDEMAND"),
        on=["REGIONID", "SETTLEMENTDATE"],
        how="outer",
    )
    tidy = merged.rename(
        columns={
            "REGIONID": "region",
            "SETTLEMENTDATE": "interval_end",
            "RRP": "price",
            "TOTALDEMAND": "demand",
        }
    )
    return tidy[ACTUALS_COLUMNS].sort_values("interval_end").reset_index(drop=True)


def find_problems(frame: pd.DataFrame, start: datetime, end: datetime) -> list[str]:
    """Return a list of quality problems. An empty list means the data is good.

    The table must hold every 5-minute interval that ends after `start`
    and at or before `end`.
    """
    problems: list[str] = []
    times = pd.DatetimeIndex(frame["interval_end"])

    duplicates = int(times.duplicated().sum())
    if duplicates:
        problems.append(f"{duplicates} duplicate interval_end values")

    expected = pd.date_range(start + INTERVAL, end, freq=INTERVAL)
    missing = expected.difference(times)
    if len(missing):
        problems.append(f"{len(missing)} missing intervals, first is {missing[0]}")

    unexpected = times.difference(expected)
    if len(unexpected):
        problems.append(f"{len(unexpected)} intervals outside the requested range")

    for column in ("price", "demand"):
        empty = int(frame[column].isna().sum())
        if empty:
            problems.append(f"{empty} empty values in {column}")

    below_floor = int((frame["price"] < MARKET_PRICE_FLOOR).sum())
    if below_floor:
        problems.append(f"{below_floor} prices below the market floor of {MARKET_PRICE_FLOOR}")

    not_positive = int((frame["demand"] <= 0).sum())
    if not_positive:
        problems.append(f"{not_positive} demand values that are zero or negative")

    return problems


def validate_actuals(frame: pd.DataFrame, start: datetime, end: datetime) -> None:
    """Raise `DataQualityError` listing every problem, or return if there is none."""
    problems = find_problems(frame, start, end)
    if problems:
        raise DataQualityError("Actuals failed quality checks: " + "; ".join(problems))
