"""AEMO pre-dispatch price forecasts: download one month and save it in the raw store.

Run from the repository root, for example for August 2026:

    python -m voltcast.ingestion.predispatch_download --year 2026 --month 8
"""

import argparse
import calendar
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from voltcast.config import Settings, get_settings
from voltcast.ingestion.predispatch import SOURCE_COLUMNS, tidy_predispatch, validate_predispatch

logger = logging.getLogger(__name__)

TABLE: str = "PREDISPATCHPRICE"
RUNS_PER_DAY: int = 48
REQUEST_HEADERS: dict[str, str] = {"User-Agent": "Mozilla/5.0 (voltcast)"}
# AEMO has used two file name styles. Both end with a 12-digit date and ".zip":
#   since August 2024:  PUBLIC_ARCHIVE#PREDISPATCHPRICE#ALL#FILE01#202608010000.zip
#   before August 2024: PUBLIC_DVD_PREDISPATCHPRICE_202401010000.zip
FILE_NAME_PATTERN: re.Pattern[str] = re.compile(
    rf"[#_]{TABLE}[#_](ALL[#_]FILE\d+[#_])?\d{{12}}\.ZIP$"
)


def archive_folder_url(year: int, month: int, settings: Settings) -> str:
    """Return the address of the AEMO folder that holds one month of pre-dispatch files."""
    return (
        f"{settings.nemweb_archive_url}/{year}/MMSDM_{year}_{month:02d}/"
        "MMSDM_Historical_Data_SQLLoader/PREDISP_ALL_DATA/"
    )


def find_file_urls(folder_page: bytes, folder_url: str) -> list[str]:
    """Read the folder page and return the full links to the files of our table."""
    soup = BeautifulSoup(folder_page, "html.parser")
    urls: list[str] = []
    for link in soup.find_all("a"):
        href = str(link.get("href") or "")
        name = href.upper().replace("%23", "#")
        if FILE_NAME_PATTERN.search(name):
            urls.append(urljoin(folder_url, href))
    return sorted(urls)


def fetch_folder_page(folder_url: str, settings: Settings) -> bytes:
    """Download the folder page."""
    response = requests.get(
        folder_url, headers=REQUEST_HEADERS, timeout=settings.request_timeout_seconds
    )
    response.raise_for_status()
    return response.content


def download_file(url: str, folder: Path, settings: Settings) -> Path:
    """Download one zip file into `folder`, unless it is already there."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / url.rsplit("/", 1)[-1].replace("%23", "_")
    if path.exists():
        logger.info("Already downloaded: %s", path.name)
        return path
    logger.info("Downloading: %s", path.name)
    temporary_path = path.with_suffix(".zip.tmp")
    with requests.get(
        url, headers=REQUEST_HEADERS, timeout=settings.request_timeout_seconds, stream=True
    ) as response:
        response.raise_for_status()
        with temporary_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file.write(chunk)
    temporary_path.replace(path)
    return path


def read_archive(path: Path) -> pd.DataFrame:
    """Read an AEMO archive zip as text columns.

    Line 1 of the file is a comment, line 2 holds the column names,
    and the last line is a footer, which has no region and is removed here.
    """
    frame = pd.read_csv(
        path,
        compression="zip",
        header=1,
        usecols=lambda column: column in SOURCE_COLUMNS,
        dtype=str,
    )
    missing = sorted(set(SOURCE_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Columns not found in {path.name}: {missing}")
    return frame.dropna(subset=["REGIONID"])


def output_path(year: int, month: int, settings: Settings) -> Path:
    """Return the raw store path for one month of pre-dispatch forecasts."""
    return settings.raw_dir / "predispatch" / f"{year}-{month:02d}.parquet"


def ingest_month(year: int, month: int, settings: Settings) -> Path:
    """Download, tidy, check and save one month. Nothing is saved if a check fails."""
    folder_url = archive_folder_url(year, month, settings)
    urls = find_file_urls(fetch_folder_page(folder_url, settings), folder_url)
    if not urls:
        raise FileNotFoundError(f"No {TABLE} file found at {folder_url}")

    archive_folder = settings.raw_dir / "predispatch" / "archive"
    raw = pd.concat(
        [read_archive(download_file(url, archive_folder, settings)) for url in urls],
        ignore_index=True,
    )

    frame = tidy_predispatch(raw, settings.region)
    validate_predispatch(frame)

    runs = frame["run_id"].nunique()
    expected_runs = calendar.monthrange(year, month)[1] * RUNS_PER_DAY
    if runs != expected_runs:
        logger.warning("Found %d runs, but a full month has %d", runs, expected_runs)

    path = output_path(year, month, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary_path, index=False)
    temporary_path.replace(path)
    logger.info("Saved %d rows from %d runs to %s", len(frame), runs, path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one month of pre-dispatch forecasts.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ingest_month(arguments.year, arguments.month, get_settings())


if __name__ == "__main__":
    main()
