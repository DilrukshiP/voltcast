"""Data check 0.7b: download one month of AEMO pre-dispatch price forecasts for VIC.

This is a one-time check, not pipeline code. It answers three questions:
1. Can we download the archive file without a special library?
2. Does the file keep every forecast run, not only the newest one?
3. Does each row tell us when the forecast was published?

Run from the repository root:  python scripts/check_predispatch.py
"""

from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

REGION: str = "VIC1"
YEAR: int = 2026
MONTH: int = 8
TABLE: str = "PREDISPATCHPRICE"
ARCHIVE_URL: str = (
    "https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/"
    f"{YEAR}/MMSDM_{YEAR}_{MONTH:02d}/MMSDM_Historical_Data_SQLLoader/PREDISP_ALL_DATA/"
)
CACHE_DIR: Path = Path("data/raw/predispatch")
COLUMNS: list[str] = [
    "PREDISPATCHSEQNO",
    "REGIONID",
    "INTERVENTION",
    "RRP",
    "DATETIME",
    "LASTCHANGED",
]
HEADERS: dict[str, str] = {"User-Agent": "Mozilla/5.0 (voltcast data check)"}
TIME_FORMAT: str = "%Y/%m/%d %H:%M:%S"


def find_file_urls() -> list[str]:
    """Read the archive folder page and return the links for our table."""
    response = requests.get(ARCHIVE_URL, headers=HEADERS, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    urls: list[str] = []
    for link in soup.find_all("a"):
        href = str(link.get("href") or "")
        name = href.upper().replace("%23", "#")
        if f"#{TABLE}#" in name and name.endswith(".ZIP"):
            urls.append(urljoin(ARCHIVE_URL, href))
    return sorted(urls)


def download(url: str) -> Path:
    """Download one zip file into the cache folder, unless it is already there."""
    file_name = url.rsplit("/", 1)[-1].replace("%23", "_")
    path = CACHE_DIR / file_name
    if path.exists():
        print(f"Already downloaded: {path.name}")
        return path
    print(f"Downloading: {path.name}")
    with requests.get(url, headers=HEADERS, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                file.write(chunk)
    print(f"  size: {path.stat().st_size / 1e6:.1f} MB")
    return path


def read_archive(path: Path) -> pd.DataFrame:
    """Read an AEMO archive file. Line 1 is a comment and line 2 holds the column names."""
    frame = pd.read_csv(
        path,
        compression="zip",
        header=1,
        usecols=lambda column: column in COLUMNS,
        dtype=str,
    )
    missing = sorted(set(COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Columns not found in {path.name}: {missing}")
    frame = frame[(frame["REGIONID"] == REGION) & (frame["INTERVENTION"] == "0")].copy()
    frame["RRP"] = frame["RRP"].astype(float)
    frame["target_time"] = pd.to_datetime(frame["DATETIME"], format=TIME_FORMAT)
    frame["published_at"] = pd.to_datetime(frame["LASTCHANGED"], format=TIME_FORMAT)
    return frame


def report(frame: pd.DataFrame) -> None:
    """Print how many runs exist and how far ahead each run forecasts."""
    horizon_hours = (frame["target_time"] - frame["published_at"]).dt.total_seconds() / 3600
    rows_per_run = frame.groupby("PREDISPATCHSEQNO").size()
    runs_per_target = frame.groupby("target_time")["PREDISPATCHSEQNO"].nunique()
    print(f"\nPre-dispatch price forecasts for {REGION}, {YEAR}-{MONTH:02d}")
    print(f"  rows:                  {len(frame)}")
    print(f"  forecast runs:         {rows_per_run.size}")
    print(f"  rows per run:          min {rows_per_run.min()}, max {rows_per_run.max()}")
    print(f"  runs per target time:  min {runs_per_target.min()}, max {runs_per_target.max()}")
    print(f"  target_time range:     {frame['target_time'].min()}, {frame['target_time'].max()}")
    print(f"  published_at range:    {frame['published_at'].min()}, {frame['published_at'].max()}")
    print(f"  horizon in hours:      min {horizon_hours.min():.2f}, max {horizon_hours.max():.2f}")
    print(f"  missing RRP:           {int(frame['RRP'].isna().sum())}")
    print(
        f"  RRP: min {frame['RRP'].min():.2f}, mean {frame['RRP'].mean():.2f}, "
        f"max {frame['RRP'].max():.2f}"
    )
    print("\nFirst rows:")
    shown = ["PREDISPATCHSEQNO", "published_at", "target_time", "RRP"]
    print(frame.sort_values(["published_at", "target_time"])[shown].head(3).to_string(index=False))


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    urls = find_file_urls()
    print(f"Files found for {TABLE}: {len(urls)}")
    if not urls:
        raise SystemExit(f"No file found. Open this page in a browser to check: {ARCHIVE_URL}")
    frames = [read_archive(download(url)) for url in urls]
    report(pd.concat(frames, ignore_index=True))


if __name__ == "__main__":
    main()
