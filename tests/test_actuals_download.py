"""Tests for the actuals download job. No test here uses the network."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from voltcast.config import Settings
from voltcast.ingestion import actuals_download
from voltcast.ingestion.actuals import ACTUALS_COLUMNS
from voltcast.ingestion.actuals_download import ingest_month, output_path
from voltcast.ingestion.quality import DataQualityError

INTERVALS_IN_AUGUST: int = 31 * 24 * 12


def make_settings(data_dir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=data_dir)


def fake_month(value_column: str, drop_last: int = 0) -> pd.DataFrame:
    """Build a full month of 5-minute rows in the shape that AEMO provides."""
    times = pd.date_range("2026-08-01 00:05", "2026-09-01 00:00", freq="5min")
    frame = pd.DataFrame(
        {
            "SETTLEMENTDATE": times,
            "REGIONID": "VIC1",
            "INTERVENTION": 0,
            value_column: 100.0,
        }
    )
    return frame.iloc[: len(frame) - drop_last]


def patch_download(monkeypatch: pytest.MonkeyPatch, drop_last: int = 0) -> None:
    """Replace the real download with hand-made tables."""

    def fake_download(
        table: str, start: datetime, end: datetime, settings: Settings
    ) -> pd.DataFrame:
        column = "RRP" if table == "DISPATCHPRICE" else "TOTALDEMAND"
        return fake_month(column, drop_last)

    monkeypatch.setattr(actuals_download, "download_table", fake_download)


def test_ingest_month_saves_a_complete_month(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_download(monkeypatch)
    settings = make_settings(tmp_path)

    path = ingest_month(2026, 8, settings)

    assert path == tmp_path / "raw" / "actuals" / "2026-08.parquet"
    saved = pd.read_parquet(path)
    assert list(saved.columns) == ACTUALS_COLUMNS
    assert len(saved) == INTERVALS_IN_AUGUST


def test_ingest_month_saves_nothing_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_download(monkeypatch, drop_last=3)
    settings = make_settings(tmp_path)

    with pytest.raises(DataQualityError, match="3 missing intervals"):
        ingest_month(2026, 8, settings)

    assert not output_path(2026, 8, settings).exists()
