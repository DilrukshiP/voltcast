"""Tests for the weather download job. No test here uses the network."""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from voltcast.config import Settings
from voltcast.ingestion import weather_download
from voltcast.ingestion.quality import DataQualityError
from voltcast.ingestion.weather import REQUESTED_API_NAMES, VARIABLES, WEATHER_COLUMNS
from voltcast.ingestion.weather_download import (
    archive_path,
    ingest_month,
    output_path,
    request_params,
)

HOURS_IN_AUGUST: int = 31 * 24


def make_settings(data_dir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=data_dir)


def month_payload(hours: int = HOURS_IN_AUGUST, utc_offset_seconds: int = 36000) -> dict[str, Any]:
    """Build a response for August 2026 in the shape that Open-Meteo returns."""
    times = pd.date_range("2026-08-01 00:00", periods=hours, freq="h")
    hourly: dict[str, list[Any]] = {"time": times.strftime("%Y-%m-%dT%H:%M").tolist()}
    units: dict[str, str] = {"time": "iso8601"}
    for name in REQUESTED_API_NAMES:
        variable = name.split("_previous_day")[0]
        hourly[name] = [10.0] * hours
        units[name] = VARIABLES[variable][1]
    return {"utc_offset_seconds": utc_offset_seconds, "hourly_units": units, "hourly": hourly}


def patch_fetch(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    """Replace the real API call with a hand-made answer."""

    def fake_fetch(year: int, month: int, settings: Settings) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(weather_download, "fetch_month", fake_fetch)


def test_request_params_cover_the_whole_month(tmp_path: Path) -> None:
    params = request_params(2026, 8, make_settings(tmp_path))
    assert params["start_date"] == "2026-08-01"
    assert params["end_date"] == "2026-08-31"
    assert params["timezone"] == "Australia/Brisbane"


def test_request_params_handle_a_leap_year(tmp_path: Path) -> None:
    assert request_params(2024, 2, make_settings(tmp_path))["end_date"] == "2024-02-29"


def test_request_params_never_ask_for_the_newest_value(tmp_path: Path) -> None:
    names = request_params(2026, 8, make_settings(tmp_path))["hourly"].split(",")
    assert len(names) == 6
    assert all("_previous_day" in name for name in names)


def test_ingest_month_saves_the_table_and_the_original_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = month_payload()
    patch_fetch(monkeypatch, payload)
    settings = make_settings(tmp_path)

    path = ingest_month(2026, 8, settings)

    assert path == tmp_path / "raw" / "weather" / "2026-08.parquet"
    saved = pd.read_parquet(path)
    assert list(saved.columns) == WEATHER_COLUMNS
    assert len(saved) == HOURS_IN_AUGUST
    assert json.loads(archive_path(2026, 8, settings).read_text(encoding="utf-8")) == payload


def test_ingest_month_saves_nothing_when_the_timezone_is_wrong(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_fetch(monkeypatch, month_payload(utc_offset_seconds=39600))
    settings = make_settings(tmp_path)

    with pytest.raises(ValidationError, match="not in market time"):
        ingest_month(2026, 8, settings)

    assert not output_path(2026, 8, settings).exists()
    assert not archive_path(2026, 8, settings).exists()


def test_ingest_month_saves_nothing_when_hours_are_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_fetch(monkeypatch, month_payload(hours=HOURS_IN_AUGUST - 2))
    settings = make_settings(tmp_path)

    with pytest.raises(DataQualityError, match="2 missing hours"):
        ingest_month(2026, 8, settings)

    assert not output_path(2026, 8, settings).exists()
    assert not archive_path(2026, 8, settings).exists()
