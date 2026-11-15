"""AEMO pre-dispatch price forecasts: turn the archive table into a clean table and check it.

This module has no network code. It only transforms and validates tables.

Words used here:
- A "run" is one forecast made by AEMO. A new run is made every 30 minutes.
- `published_at` is when AEMO wrote the run. A forecast may be used only after this time.
- `target_time` is the end of the half hour that a row forecasts.
"""

import pandas as pd

from voltcast.ingestion.quality import DataQualityError

STEP: pd.Timedelta = pd.Timedelta(minutes=30)
MAX_HORIZON: pd.Timedelta = pd.Timedelta(hours=48)
MARKET_PRICE_FLOOR: float = -1000.0  # dollars per MWh, set by the market rules
AEMO_TIME_FORMAT: str = "%Y/%m/%d %H:%M:%S"
SOURCE_COLUMNS: list[str] = [
    "PREDISPATCHSEQNO",
    "REGIONID",
    "INTERVENTION",
    "RRP",
    "DATETIME",
    "LASTCHANGED",
]
PREDISPATCH_COLUMNS: list[str] = [
    "region",
    "run_id",
    "published_at",
    "target_time",
    "forecast_price",
]


def tidy_predispatch(raw: pd.DataFrame, region: str) -> pd.DataFrame:
    """Keep one region and the normal market run, convert text to real types, and rename.

    `raw` holds the columns in `SOURCE_COLUMNS`, all as text, as read from the archive file.
    """
    keep = (raw["REGIONID"] == region) & (raw["INTERVENTION"] == "0")
    selected = raw.loc[keep]
    tidy = pd.DataFrame(
        {
            "region": selected["REGIONID"],
            "run_id": selected["PREDISPATCHSEQNO"],
            "published_at": pd.to_datetime(selected["LASTCHANGED"], format=AEMO_TIME_FORMAT),
            "target_time": pd.to_datetime(selected["DATETIME"], format=AEMO_TIME_FORMAT),
            "forecast_price": pd.to_numeric(selected["RRP"]),
        }
    )
    return tidy.sort_values(["published_at", "target_time"]).reset_index(drop=True)


def find_problems(frame: pd.DataFrame) -> list[str]:
    """Return a list of quality problems. An empty list means the data is good."""
    if frame.empty:
        return ["the table has no rows"]

    problems: list[str] = []

    duplicates = int(frame.duplicated(subset=["run_id", "target_time"]).sum())
    if duplicates:
        problems.append(f"{duplicates} duplicate rows for the same run and target_time")

    empty = int(frame["forecast_price"].isna().sum())
    if empty:
        problems.append(f"{empty} empty values in forecast_price")

    below_floor = int((frame["forecast_price"] < MARKET_PRICE_FLOOR).sum())
    if below_floor:
        problems.append(f"{below_floor} prices below the market floor of {MARKET_PRICE_FLOOR}")

    horizon = frame["target_time"] - frame["published_at"]
    not_ahead = int((horizon <= pd.Timedelta(0)).sum())
    if not_ahead:
        problems.append(f"{not_ahead} rows where published_at is not before target_time")

    too_far = int((horizon > MAX_HORIZON).sum())
    if too_far:
        problems.append(f"{too_far} rows that forecast more than {MAX_HORIZON} ahead")

    off_grid = int((frame["target_time"].dt.floor("30min") != frame["target_time"]).sum())
    if off_grid:
        problems.append(f"{off_grid} target_time values that are not on a half hour")

    publish_times_per_run = frame.groupby("run_id")["published_at"].nunique()
    mixed_runs = int((publish_times_per_run > 1).sum())
    if mixed_runs:
        problems.append(f"{mixed_runs} runs with more than one published_at")

    ordered = frame.sort_values(["run_id", "target_time"])
    step = ordered.groupby("run_id")["target_time"].diff().dropna()
    gaps = int((step != STEP).sum())
    if gaps:
        problems.append(f"{gaps} gaps between target_time values inside a run")

    return problems


def validate_predispatch(frame: pd.DataFrame) -> None:
    """Raise `DataQualityError` listing every problem, or return if there is none."""
    problems = find_problems(frame)
    if problems:
        raise DataQualityError("Pre-dispatch failed quality checks: " + "; ".join(problems))
