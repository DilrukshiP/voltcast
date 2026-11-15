"""Data check 0.7a: download one week of actual VIC prices and demand from AEMO.

This is a one-time check, not pipeline code. It answers three questions:
1. Can we download the data on this machine?
2. Is every 5-minute interval present?
3. Do the values look reasonable?

Run from the repository root:  python scripts/check_actuals.py
"""

from pathlib import Path

import pandas as pd
from nemosis import dynamic_data_compiler

REGION: str = "VIC1"
START: str = "2026/08/01 00:00:00"
END: str = "2026/08/08 00:00:00"
CACHE_DIR: Path = Path("data/raw/nemosis")
EXPECTED_ROWS: int = 7 * 24 * 12  # 7 days of 5-minute intervals


def download(table: str, columns: list[str]) -> pd.DataFrame:
    """Download one AEMO table for the check week, VIC only, no intervention runs."""
    frame: pd.DataFrame = dynamic_data_compiler(
        START,
        END,
        table,
        str(CACHE_DIR),
        select_columns=["SETTLEMENTDATE", "REGIONID", "INTERVENTION", *columns],
        filter_cols=["REGIONID", "INTERVENTION"],
        filter_values=([REGION], [0]),
        fformat="parquet",
        keep_csv=False,
    )
    return frame.sort_values("SETTLEMENTDATE").reset_index(drop=True)


def report(name: str, frame: pd.DataFrame, value_column: str) -> None:
    """Print row count, time range, gaps, duplicates and value range."""
    times: pd.Series = frame["SETTLEMENTDATE"]
    gaps: int = int((times.diff().dropna() != pd.Timedelta(minutes=5)).sum())
    print(f"\n{name}")
    print(f"  rows:        {len(frame)} (expected {EXPECTED_ROWS})")
    print(f"  first, last: {times.min()}, {times.max()}")
    print(f"  gaps:        {gaps}")
    print(f"  duplicates:  {int(times.duplicated().sum())}")
    print(f"  missing:     {int(frame[value_column].isna().sum())}")
    print(
        f"  {value_column}: min {frame[value_column].min():.2f}, "
        f"mean {frame[value_column].mean():.2f}, max {frame[value_column].max():.2f}"
    )


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prices = download("DISPATCHPRICE", ["RRP"])
    demand = download("DISPATCHREGIONSUM", ["TOTALDEMAND"])
    report("Prices (DISPATCHPRICE, dollars per MWh)", prices, "RRP")
    report("Demand (DISPATCHREGIONSUM, MW)", demand, "TOTALDEMAND")
    print("\nFirst rows of prices:")
    print(prices.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
