"""Tests for the backfill command. The jobs here are hand-made, so nothing is downloaded."""

from pathlib import Path

from voltcast.config import Settings
from voltcast.ingestion.backfill import JOBS, Job, backfill

MONTHS = [(2026, 7), (2026, 8)]


def make_settings(data_dir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=data_dir)


def fake_job(name: str, calls: list[str], fail_month: int | None = None) -> Job:
    """Build a job that writes a small file, records each call, and can fail for one month."""

    def output_path(year: int, month: int, settings: Settings) -> Path:
        return settings.raw_dir / name / f"{year}-{month:02d}.parquet"

    def ingest_month(year: int, month: int, settings: Settings) -> Path:
        calls.append(f"{name} {year}-{month:02d}")
        if month == fail_month:
            raise ValueError("bad data")
        path = output_path(year, month, settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("saved")
        return path

    return Job(ingest_month, output_path)


def test_real_jobs_cover_the_three_sources() -> None:
    assert sorted(JOBS) == ["actuals", "predispatch", "weather"]


def test_backfill_runs_every_job_for_every_month(tmp_path: Path) -> None:
    calls: list[str] = []
    jobs = {"a": fake_job("a", calls), "b": fake_job("b", calls)}

    report = backfill(MONTHS, make_settings(tmp_path), jobs)

    assert report.saved == ["a 2026-07", "b 2026-07", "a 2026-08", "b 2026-08"]
    assert report.skipped == []
    assert report.failed == {}


def test_second_run_skips_months_that_are_already_saved(tmp_path: Path) -> None:
    calls: list[str] = []
    jobs = {"a": fake_job("a", calls)}
    settings = make_settings(tmp_path)
    backfill(MONTHS, settings, jobs)
    calls.clear()

    report = backfill(MONTHS, settings, jobs)

    assert calls == []
    assert report.skipped == ["a 2026-07", "a 2026-08"]
    assert report.saved == []


def test_force_runs_months_that_are_already_saved(tmp_path: Path) -> None:
    calls: list[str] = []
    jobs = {"a": fake_job("a", calls)}
    settings = make_settings(tmp_path)
    backfill(MONTHS, settings, jobs)
    calls.clear()

    report = backfill(MONTHS, settings, jobs, force=True)

    assert calls == ["a 2026-07", "a 2026-08"]
    assert report.saved == ["a 2026-07", "a 2026-08"]


def test_one_failure_is_reported_and_other_months_still_run(tmp_path: Path) -> None:
    calls: list[str] = []
    jobs = {"a": fake_job("a", calls, fail_month=7), "b": fake_job("b", calls)}

    report = backfill(MONTHS, make_settings(tmp_path), jobs)

    assert report.failed == {"a 2026-07": "ValueError: bad data"}
    assert report.saved == ["b 2026-07", "a 2026-08", "b 2026-08"]
    assert len(calls) == 4
