"""Tests for the pre-dispatch download job. No test here uses the network."""

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from voltcast.config import Settings
from voltcast.ingestion import predispatch_download
from voltcast.ingestion.predispatch import PREDISPATCH_COLUMNS
from voltcast.ingestion.predispatch_download import (
    archive_folder_url,
    find_file_urls,
    ingest_month,
    output_path,
    read_archive,
)
from voltcast.ingestion.quality import DataQualityError

FOLDER_URL = "https://example.test/2026/PREDISP_ALL_DATA/"
NEW_STYLE_NAME = "PUBLIC_ARCHIVE%23PREDISPATCHPRICE%23ALL%23FILE01%23202608010000.zip"
OLD_STYLE_NAME = "PUBLIC_DVD_PREDISPATCHPRICE_202401010000.zip"

HEADER = (
    "I,PREDISPATCH,REGION_PRICES,2,PREDISPATCHSEQNO,RUNNO,REGIONID,PERIODID,"
    "INTERVENTION,RRP,DATETIME,LASTCHANGED"
)


def make_settings(data_dir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=data_dir)


def folder_page(*file_names: str) -> bytes:
    links = "".join(
        f'<a href="/2026/PREDISP_ALL_DATA/{name}">{name}</a><br>' for name in file_names
    )
    return f"<html><body>{links}</body></html>".encode()


def data_row(run_id: str, region: str, price: str, target: str, published: str) -> str:
    return (
        f'D,PREDISPATCH,REGION_PRICES,2,"{run_id}",1,{region},1,0,{price},"{target}","{published}"'
    )


def write_archive(path: Path, rows: list[str]) -> Path:
    """Write a zip file in the layout of an AEMO archive file."""
    lines = ["C,NEMP.WORLD,ARCHIVE,AEMO,PUBLIC", HEADER, *rows, f"C,END OF REPORT,{len(rows) + 3}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data.CSV", "\n".join(lines) + "\n")
    return path


def good_rows() -> list[str]:
    published = "2026/08/01 04:01:23"
    return [
        data_row("2026080101", "VIC1", "75.4", "2026/08/01 04:30:00", published),
        data_row("2026080101", "NSW1", "60.0", "2026/08/01 04:30:00", published),
        data_row("2026080101", "VIC1", "80.5", "2026/08/01 05:00:00", published),
        data_row("2026080101", "NSW1", "61.0", "2026/08/01 05:00:00", published),
    ]


def patch_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rows: list[str]) -> None:
    """Replace both network functions with local hand-made data."""
    archive = write_archive(tmp_path / "source" / "file.zip", rows)

    def fake_page(folder_url: str, settings: Settings) -> bytes:
        return folder_page(NEW_STYLE_NAME)

    def fake_download(url: str, folder: Path, settings: Settings) -> Path:
        return archive

    monkeypatch.setattr(predispatch_download, "fetch_folder_page", fake_page)
    monkeypatch.setattr(predispatch_download, "download_file", fake_download)


def test_archive_folder_url_has_year_and_two_digit_month(tmp_path: Path) -> None:
    url = archive_folder_url(2026, 8, make_settings(tmp_path))
    assert url.endswith("/2026/MMSDM_2026_08/MMSDM_Historical_Data_SQLLoader/PREDISP_ALL_DATA/")


def test_find_file_urls_accepts_the_new_file_name_style() -> None:
    urls = find_file_urls(folder_page(NEW_STYLE_NAME), FOLDER_URL)
    assert urls == [f"https://example.test/2026/PREDISP_ALL_DATA/{NEW_STYLE_NAME}"]


def test_find_file_urls_accepts_the_old_file_name_style() -> None:
    urls = find_file_urls(folder_page(OLD_STYLE_NAME), FOLDER_URL)
    assert urls == [f"https://example.test/2026/PREDISP_ALL_DATA/{OLD_STYLE_NAME}"]


def test_find_file_urls_ignores_other_tables() -> None:
    page = folder_page(
        "PUBLIC_ARCHIVE%23PREDISPATCHPRICESENSITIVITIES%23ALL%23FILE01%23202608010000.zip",
        "PUBLIC_ARCHIVE%23PREDISPATCHREGIONSUM%23ALL%23FILE01%23202608010000.zip",
        "PUBLIC_DVD_PREDISPATCHPRICESENSITIVITIES_202401010000.zip",
    )
    assert find_file_urls(page, FOLDER_URL) == []


def test_find_file_urls_returns_every_part_in_order() -> None:
    second = NEW_STYLE_NAME.replace("FILE01", "FILE02")
    urls = find_file_urls(folder_page(second, NEW_STYLE_NAME), FOLDER_URL)
    assert [url.rsplit("/", 1)[-1] for url in urls] == [NEW_STYLE_NAME, second]


def test_read_archive_skips_comment_and_footer_lines(tmp_path: Path) -> None:
    frame = read_archive(write_archive(tmp_path / "file.zip", good_rows()))
    assert len(frame) == 4
    assert frame["PREDISPATCHSEQNO"].tolist() == ["2026080101"] * 4
    assert frame["RRP"].tolist() == ["75.4", "60.0", "80.5", "61.0"]


def test_read_archive_reports_a_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "file.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data.CSV", "C,comment\nI,PREDISPATCH,X,1,REGIONID,RRP\nD,P,X,1,VIC1,5\n")
    with pytest.raises(ValueError, match="Columns not found"):
        read_archive(path)


def test_ingest_month_saves_only_our_region(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_network(monkeypatch, tmp_path, good_rows())
    settings = make_settings(tmp_path)

    path = ingest_month(2026, 8, settings)

    assert path == tmp_path / "raw" / "predispatch" / "2026-08.parquet"
    saved = pd.read_parquet(path)
    assert list(saved.columns) == PREDISPATCH_COLUMNS
    assert saved["region"].tolist() == ["VIC1", "VIC1"]
    assert saved["forecast_price"].tolist() == [75.4, 80.5]


def test_ingest_month_saves_nothing_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    late = data_row("2026080101", "VIC1", "75.4", "2026/08/01 04:00:00", "2026/08/01 04:01:23")
    patch_network(monkeypatch, tmp_path, [late])
    settings = make_settings(tmp_path)

    with pytest.raises(DataQualityError, match="published_at is not before target_time"):
        ingest_month(2026, 8, settings)

    assert not output_path(2026, 8, settings).exists()


def test_ingest_month_fails_clearly_when_no_file_is_listed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def empty_page(folder_url: str, settings: Settings) -> bytes:
        return folder_page()

    monkeypatch.setattr(predispatch_download, "fetch_folder_page", empty_page)

    with pytest.raises(FileNotFoundError, match="No PREDISPATCHPRICE file found"):
        ingest_month(2026, 8, make_settings(tmp_path))
