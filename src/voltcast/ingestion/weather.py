"""Weather forecasts: validate the Open-Meteo response, turn it into a clean table, check it.

This module has no network code.

We keep two versions of each variable:
- `day1`: the forecast made about one day before the target hour.
- `day2`: the forecast made about two days before the target hour.

We do not keep the newest value. It is made close to the target hour, so it holds
information that did not exist when our forecast is issued.
"""

from datetime import datetime
from typing import Self

import pandas as pd
from pydantic import BaseModel, model_validator

from voltcast.ingestion.quality import DataQualityError

STEP: pd.Timedelta = pd.Timedelta(hours=1)
MARKET_UTC_OFFSET_SECONDS: int = 10 * 3600  # market time is UTC+10 all year

# Open-Meteo name -> (our name, expected unit, lowest allowed value, highest allowed value)
VARIABLES: dict[str, tuple[str, str, float, float]] = {
    "temperature_2m": ("temperature", "°C", -25.0, 55.0),
    "wind_speed_10m": ("wind_speed", "km/h", 0.0, 250.0),
    "shortwave_radiation": ("solar_radiation", "W/m²", 0.0, 1500.0),
}
LEAD_DAYS: tuple[int, ...] = (1, 2)


def api_name(variable: str, lead_day: int) -> str:
    """Return the Open-Meteo name of a variable as forecast `lead_day` days earlier."""
    return f"{variable}_previous_day{lead_day}"


def column_name(variable: str, lead_day: int) -> str:
    """Return our column name for a variable and lead day, for example `temperature_day1`."""
    return f"{VARIABLES[variable][0]}_day{lead_day}"


REQUESTED_API_NAMES: list[str] = [
    api_name(variable, lead_day) for variable in VARIABLES for lead_day in LEAD_DAYS
]
VALUE_COLUMNS: list[str] = [
    column_name(variable, lead_day) for variable in VARIABLES for lead_day in LEAD_DAYS
]
WEATHER_COLUMNS: list[str] = ["target_time", *VALUE_COLUMNS]


class WeatherResponse(BaseModel):
    """The parts of the Open-Meteo response that we use, with checks on its structure."""

    utc_offset_seconds: int
    hourly_units: dict[str, str]
    hourly: dict[str, list[float | str | None]]

    @model_validator(mode="after")
    def structure_is_as_expected(self) -> Self:
        if self.utc_offset_seconds != MARKET_UTC_OFFSET_SECONDS:
            raise ValueError(
                f"times are not in market time: utc_offset_seconds is {self.utc_offset_seconds}"
            )
        if "time" not in self.hourly:
            raise ValueError("hourly has no 'time' list")
        length = len(self.hourly["time"])
        for variable, (_, unit, _, _) in VARIABLES.items():
            for lead_day in LEAD_DAYS:
                name = api_name(variable, lead_day)
                if name not in self.hourly:
                    raise ValueError(f"hourly has no '{name}' list")
                if len(self.hourly[name]) != length:
                    raise ValueError(f"'{name}' has a different length from 'time'")
                if self.hourly_units.get(name) != unit:
                    raise ValueError(
                        f"'{name}' has unit {self.hourly_units.get(name)!r}, expected {unit!r}"
                    )
        return self


def tidy_weather(response: WeatherResponse) -> pd.DataFrame:
    """Turn a validated response into a table with one row per hour and our column names."""
    data: dict[str, pd.Series] = {
        "target_time": pd.to_datetime(pd.Series(response.hourly["time"]), format="%Y-%m-%dT%H:%M")
    }
    for variable in VARIABLES:
        for lead_day in LEAD_DAYS:
            values = pd.Series(response.hourly[api_name(variable, lead_day)])
            data[column_name(variable, lead_day)] = pd.to_numeric(values)
    return pd.DataFrame(data)[WEATHER_COLUMNS].sort_values("target_time").reset_index(drop=True)


def find_problems(frame: pd.DataFrame, start: datetime, end: datetime) -> list[str]:
    """Return a list of quality problems. An empty list means the data is good.

    The table must hold every hour from `start` up to, but not including, `end`.
    """
    problems: list[str] = []
    times = pd.DatetimeIndex(frame["target_time"])

    duplicates = int(times.duplicated().sum())
    if duplicates:
        problems.append(f"{duplicates} duplicate target_time values")

    expected = pd.date_range(start, end, freq=STEP, inclusive="left")
    missing = expected.difference(times)
    if len(missing):
        problems.append(f"{len(missing)} missing hours, first is {missing[0]}")

    unexpected = times.difference(expected)
    if len(unexpected):
        problems.append(f"{len(unexpected)} hours outside the requested range")

    for variable, (_, _, lowest, highest) in VARIABLES.items():
        for lead_day in LEAD_DAYS:
            column = column_name(variable, lead_day)
            empty = int(frame[column].isna().sum())
            if empty:
                problems.append(f"{empty} empty values in {column}")
            out_of_range = int(((frame[column] < lowest) | (frame[column] > highest)).sum())
            if out_of_range:
                problems.append(f"{out_of_range} values in {column} outside {lowest} to {highest}")

    return problems


def validate_weather(frame: pd.DataFrame, start: datetime, end: datetime) -> None:
    """Raise `DataQualityError` listing every problem, or return if there is none."""
    problems = find_problems(frame, start, end)
    if problems:
        raise DataQualityError("Weather failed quality checks: " + "; ".join(problems))
