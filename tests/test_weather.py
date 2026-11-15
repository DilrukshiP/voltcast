"""Tests for the weather response model, transform and checks."""

from datetime import datetime
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from voltcast.ingestion.quality import DataQualityError
from voltcast.ingestion.weather import (
    REQUESTED_API_NAMES,
    VARIABLES,
    WEATHER_COLUMNS,
    WeatherResponse,
    find_problems,
    tidy_weather,
    validate_weather,
)

START = datetime(2026, 8, 1, 0, 0)
END = datetime(2026, 8, 1, 3, 0)  # three hours: 00:00, 01:00, 02:00
TIMES = ["2026-08-01T00:00", "2026-08-01T01:00", "2026-08-01T02:00"]


def payload() -> dict[str, Any]:
    """Build a small response in the shape that Open-Meteo returns."""
    hourly: dict[str, list[Any]] = {"time": list(TIMES)}
    units: dict[str, str] = {"time": "iso8601"}
    for name in REQUESTED_API_NAMES:
        variable = name.split("_previous_day")[0]
        hourly[name] = [5.0, 4.5, 4.0]
        units[name] = VARIABLES[variable][1]
    return {
        "latitude": -37.8,
        "utc_offset_seconds": 36000,
        "hourly_units": units,
        "hourly": hourly,
    }


def good_frame() -> pd.DataFrame:
    return tidy_weather(WeatherResponse.model_validate(payload()))


def test_valid_response_is_accepted_and_extra_fields_are_ignored() -> None:
    response = WeatherResponse.model_validate(payload())
    assert response.utc_offset_seconds == 36000


def test_response_in_another_timezone_is_rejected() -> None:
    data = payload()
    data["utc_offset_seconds"] = 39600  # Melbourne daylight saving time
    with pytest.raises(ValidationError, match="not in market time"):
        WeatherResponse.model_validate(data)


def test_response_with_a_missing_variable_is_rejected() -> None:
    data = payload()
    del data["hourly"]["temperature_2m_previous_day2"]
    with pytest.raises(ValidationError, match="no 'temperature_2m_previous_day2' list"):
        WeatherResponse.model_validate(data)


def test_response_with_a_changed_unit_is_rejected() -> None:
    data = payload()
    data["hourly_units"]["wind_speed_10m_previous_day1"] = "mp/h"
    with pytest.raises(ValidationError, match="expected 'km/h'"):
        WeatherResponse.model_validate(data)


def test_response_with_lists_of_different_length_is_rejected() -> None:
    data = payload()
    data["hourly"]["shortwave_radiation_previous_day1"] = [0.0, 0.0]
    with pytest.raises(ValidationError, match="different length"):
        WeatherResponse.model_validate(data)


def test_tidy_weather_uses_our_column_names_and_real_types() -> None:
    frame = good_frame()
    assert list(frame.columns) == WEATHER_COLUMNS
    assert "temperature_day1" in frame.columns
    assert "solar_radiation_day2" in frame.columns
    assert frame["target_time"].tolist() == list(pd.to_datetime(TIMES))
    assert frame["temperature_day1"].tolist() == [5.0, 4.5, 4.0]


def test_good_data_has_no_problems() -> None:
    assert find_problems(good_frame(), START, END) == []
    validate_weather(good_frame(), START, END)


def test_missing_hour_is_reported() -> None:
    frame = good_frame().drop(index=1)
    assert find_problems(frame, START, END) == ["1 missing hours, first is 2026-08-01 01:00:00"]


def test_empty_value_from_the_api_is_reported() -> None:
    data = payload()
    data["hourly"]["wind_speed_10m_previous_day2"] = [5.0, None, 4.0]
    frame = tidy_weather(WeatherResponse.model_validate(data))
    assert find_problems(frame, START, END) == ["1 empty values in wind_speed_day2"]


def test_value_outside_the_allowed_range_is_reported() -> None:
    frame = good_frame()
    frame.loc[0, "solar_radiation_day1"] = -3.0
    problems = find_problems(frame, START, END)
    assert problems == ["1 values in solar_radiation_day1 outside 0.0 to 1500.0"]


def test_validate_raises_with_every_problem_listed() -> None:
    frame = good_frame().drop(index=2)
    frame.loc[0, "temperature_day1"] = 80.0
    with pytest.raises(DataQualityError) as error:
        validate_weather(frame, START, END)
    message = str(error.value)
    assert "missing hours" in message
    assert "temperature_day1 outside" in message
