"""Actual prices and demand: download one month from AEMO and save it in the raw store.

Run from the repository root, for example for August 2026:

    python -m voltcast.ingestion.actuals_download --year 2026 --month 8
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from nemosis import dynamic_data_compiler

from voltcast.config import Settings, get_settings
from voltcast.ingestion.actuals import tidy_actuals, validate_actuals

logger = logging.getLogger(__name__)

NEMOSIS_TIME_FORMAT: str = "%Y/%m/%d %H:%M:%S"


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Return midnight on the first day of the month and of the next month."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def download_table(table: str, start: datetime, end: datetime, settings: Settings) -> pd.DataFrame:
    """Download one AEMO table for the time range. NEMOSIS keeps its own file cache."""
    cache_dir = settings.raw_dir / "nemosis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    frame: pd.DataFrame = dynamic_data_compiler(
        start.strftime(NEMOSIS_TIME_FORMAT),
        end.strftime(NEMOSIS_TIME_FORMAT),
        table,
        str(cache_dir),
        fformat="parquet",
        keep_csv=False,
    )
    return frame


def output_path(year: int, month: int, settings: Settings) -> Path:
    """Return the raw store path for one month of actuals."""
    return settings.raw_dir / "actuals" / f"{year}-{month:02d}.parquet"


def ingest_month(year: int, month: int, settings: Settings) -> Path:
    """Download, tidy, check and save one month. Nothing is saved if a check fails."""
    start, end = month_bounds(year, month)
    prices = download_table("DISPATCHPRICE", start, end, settings)
    demand = download_table("DISPATCHREGIONSUM", start, end, settings)

    frame = tidy_actuals(prices, demand, settings.region)
    validate_actuals(frame, start, end)

    path = output_path(year, month, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary_path, index=False)
    temporary_path.replace(path)
    logger.info("Saved %d rows to %s", len(frame), path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one month of actual prices and demand.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ingest_month(arguments.year, arguments.month, get_settings())


if __name__ == "__main__":
    main()
