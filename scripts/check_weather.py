"""Data check 0.7c: download one week of weather forecasts for Melbourne from Open-Meteo.

This is a one-time check, not pipeline code. It answers three questions:
1. Can we download past weather forecasts without an API key?
2. Is every hour present?
3. Do we get the forecast made one day earlier, not only the newest value?

Run from the repository root:  python scripts/check_weather.py
"""

from typing import Any

import pandas as pd
import requests

API_URL: str = "https://previous-runs-api.open-meteo.com/v1/forecast"
LATITUDE: float = -37.81  # Melbourne
LONGITUDE: float = 144.96
START_DATE: str = "2026-08-01"
END_DATE: str = "2026-08-07"
# Brisbane time is UTC+10 all year, the same as AEMO market time.
MARKET_TIMEZONE: str = "Australia/Brisbane"
VARIABLES: list[str] = ["temperature_2m", "wind_speed_10m", "shortwave_radiation"]
DAY_AHEAD_SUFFIX: str = "_previous_day1"
EXPECTED_ROWS: int = 7 * 24


def fetch() -> dict[str, Any]:
    """Request the newest value and the day-ahead forecast for each variable."""
    hourly = VARIABLES + [name + DAY_AHEAD_SUFFIX for name in VARIABLES]
    params: dict[str, str | float] = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(hourly),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "timezone": MARKET_TIMEZONE,
    }
    response = requests.get(API_URL, params=params, timeout=60)
    if not response.ok:
        raise SystemExit(f"Request failed with status {response.status_code}: {response.text}")
    payload: dict[str, Any] = response.json()
    return payload


def to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    """Turn the 'hourly' part of the response into a table with one row per hour."""
    frame = pd.DataFrame(payload["hourly"])
    frame["time"] = pd.to_datetime(frame["time"])
    return frame.rename(columns={"time": "target_time"})


def report(frame: pd.DataFrame, units: dict[str, str]) -> None:
    """Print row count, gaps and, for each variable, how the two versions differ."""
    times = frame["target_time"]
    gaps = int((times.diff().dropna() != pd.Timedelta(hours=1)).sum())
    print("Weather forecasts for Melbourne")
    print(f"  rows:        {len(frame)} (expected {EXPECTED_ROWS})")
    print(f"  first, last: {times.min()}, {times.max()}")
    print(f"  gaps:        {gaps}")
    for name in VARIABLES:
        newest = frame[name]
        day_ahead = frame[name + DAY_AHEAD_SUFFIX]
        difference = (newest - day_ahead).abs().mean()
        print(f"\n  {name} ({units.get(name, '?')})")
        missing_newest = int(newest.isna().sum())
        missing_day_ahead = int(day_ahead.isna().sum())
        print(f"    missing newest, day ahead: {missing_newest}, {missing_day_ahead}")
        print(
            f"    day ahead: min {day_ahead.min():.1f}, "
            f"mean {day_ahead.mean():.1f}, max {day_ahead.max():.1f}"
        )
        print(f"    mean absolute difference between the two: {difference:.2f}")
    print("\nFirst rows:")
    shown = ["target_time", "temperature_2m", "temperature_2m" + DAY_AHEAD_SUFFIX]
    print(frame[shown].head(3).to_string(index=False))


def main() -> None:
    payload = fetch()
    report(to_frame(payload), payload.get("hourly_units", {}))


if __name__ == "__main__":
    main()
