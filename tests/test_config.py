"""Tests for the settings module."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from voltcast.config import Settings


def make_settings() -> Settings:
    """Build settings without reading a local `.env` file, so tests are repeatable."""
    return Settings(_env_file=None)


def test_defaults_describe_victoria() -> None:
    settings = make_settings()
    assert settings.region == "VIC1"
    assert settings.market_timezone == "Australia/Brisbane"
    assert settings.history_start == date(2024, 1, 1)
    assert settings.raw_dir == Path("data") / "raw"


def test_environment_variable_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLTCAST_DATA_DIR", "/tmp/voltcast-data")
    assert make_settings().data_dir == Path("/tmp/voltcast-data")


def test_unknown_region_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLTCAST_REGION", "WA1")
    with pytest.raises(ValidationError):
        make_settings()


def test_history_start_before_weather_history_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VOLTCAST_HISTORY_START", "2023-12-31")
    with pytest.raises(ValidationError):
        make_settings()


def test_settings_cannot_be_changed_after_creation() -> None:
    settings = make_settings()
    with pytest.raises(ValidationError):
        settings.region = "NSW1"  # type: ignore[misc]
