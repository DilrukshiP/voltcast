"""Backfill: run the monthly ingestion jobs for a range of months.

Run from the repository root, for example:

    python -m voltcast.ingestion.backfill --from 2026-05 --to 2026-07

A month that is already saved is skipped, so the command can be run again safely.
A month that fails is reported at the end, and the other months still run.
"""

import argparse
import logging
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from voltcast.config import Settings, get_settings
from voltcast.ingestion import actuals_download, predispatch_download, weather_download
from voltcast.ingestion.periods import months_between, parse_month

logger = logging.getLogger(__name__)

MonthFunction = Callable[[int, int, Settings], Path]


class Job(NamedTuple):
    """One source: how to ingest a month, and where that month is saved."""

    ingest_month: MonthFunction
    output_path: MonthFunction


JOBS: dict[str, Job] = {
    "actuals": Job(actuals_download.ingest_month, actuals_download.output_path),
    "predispatch": Job(predispatch_download.ingest_month, predispatch_download.output_path),
    "weather": Job(weather_download.ingest_month, weather_download.output_path),
}


@dataclass
class BackfillReport:
    """What happened to each source and month. Each entry looks like 'weather 2026-08'."""

    saved: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def backfill(
    months: list[tuple[int, int]],
    settings: Settings,
    jobs: Mapping[str, Job] = JOBS,
    force: bool = False,
) -> BackfillReport:
    """Run every job for every month. One failure does not stop the other months."""
    report = BackfillReport()
    for year, month in months:
        for name, job in jobs.items():
            label = f"{name} {year}-{month:02d}"
            if not force and job.output_path(year, month, settings).exists():
                report.skipped.append(label)
                continue
            try:
                job.ingest_month(year, month, settings)
            except Exception as error:
                logger.error("%s failed: %s", label, error)
                report.failed[label] = f"{type(error).__name__}: {error}"
            else:
                report.saved.append(label)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a range of months for all sources.")
    parser.add_argument("--from", dest="first", required=True, help="first month, as YYYY-MM")
    parser.add_argument("--to", dest="last", required=True, help="last month, as YYYY-MM")
    parser.add_argument("--source", choices=sorted(JOBS), action="append", help="default: all")
    parser.add_argument("--force", action="store_true", help="download months that already exist")
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    months = months_between(parse_month(arguments.first), parse_month(arguments.last))
    jobs = {name: JOBS[name] for name in (arguments.source or JOBS)}
    report = backfill(months, get_settings(), jobs, arguments.force)

    print(f"\nSaved:   {len(report.saved)}")
    print(f"Skipped: {len(report.skipped)} (already saved)")
    print(f"Failed:  {len(report.failed)}")
    for label, message in report.failed.items():
        print(f"  {label}: {message}")
    if report.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
