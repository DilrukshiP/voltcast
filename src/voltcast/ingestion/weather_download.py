"""Weather forecasts: download one month from Open-Meteo and save it in the raw store.

Run from the repository root, for example for August 2026:

    python -m voltcast.ingestion.weather_download --year 2026 --month 8
"""

import argparse
import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import requests

from voltcast.config import Settings, get_settings
from voltcast.ingestion.periods import month_bounds
from voltcast.ingestion.weather import (
    REQUESTED_API_NAMES,
    WeatherResponse,
    tidy_weather,
    validate_weather,
)

logger = logging.getLogger(__name__)


def request_params(year: int, month: int, settings: Settings) -> dict[str, str]:
    """Build the query for one month. The API includes both the start and the end date."""
    start, end = month_bounds(year, month)
    last_day = end - timedelta(days=1)
    return {
        "latitude": str(settings.latitude),
        "longitude": str(settings.longitude),
        "hourly": ",".join(REQUESTED_API_NAMES),
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": last_day.strftime("%Y-%m-%d"),
        "timezone": settings.market_timezone,
    }


def fetch_month(year: int, month: int, settings: Settings) -> dict[str, Any]:
    """Call the weather API and return its answer as a dictionary."""
    response = requests.get(
        settings.weather_api_url,
        params=request_params(year, month, settings),
        timeout=settings.request_timeout_seconds,
    )
    if not response.ok:
        raise RuntimeError(
            f"Weather request failed with status {response.status_code}: {response.text}"
        )
    payload: dict[str, Any] = response.json()
    return payload


def output_path(year: int, month: int, settings: Settings) -> Path:
    """Return the raw store path for one month of weather forecasts."""
    return settings.raw_dir / "weather" / f"{year}-{month:02d}.parquet"


def archive_path(year: int, month: int, settings: Settings) -> Path:
    """Return where the unchanged API answer for one month is kept."""
    return settings.raw_dir / "weather" / "archive" / f"{year}-{month:02d}.json"


def ingest_month(year: int, month: int, settings: Settings) -> Path:
    """Download, validate, tidy, check and save one month. Nothing is saved if a check fails."""
    start, end = month_bounds(year, month)
    payload = fetch_month(year, month, settings)

    response = WeatherResponse.model_validate(payload)
    frame = tidy_weather(response)
    validate_weather(frame, start, end)

    original = archive_path(year, month, settings)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(json.dumps(payload), encoding="utf-8")

    path = output_path(year, month, settings)
    temporary_path = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary_path, index=False)
    temporary_path.replace(path)
    logger.info("Saved %d rows to %s", len(frame), path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one month of weather forecasts.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ingest_month(arguments.year, arguments.month, get_settings())


if __name__ == "__main__":
    main()
