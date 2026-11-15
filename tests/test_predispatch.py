"""Tests for the pre-dispatch transform and checks."""

import pandas as pd
import pytest

from voltcast.ingestion.predispatch import (
    PREDISPATCH_COLUMNS,
    find_problems,
    tidy_predispatch,
    validate_predispatch,
)
from voltcast.ingestion.quality import DataQualityError


def raw_run(
    run_id: str,
    published: str,
    targets: list[str],
    prices: list[str],
    region: str = "VIC1",
    intervention: str = "0",
) -> pd.DataFrame:
    """Build one forecast run as text columns, in the shape of the AEMO archive file."""
    return pd.DataFrame(
        {
            "PREDISPATCHSEQNO": run_id,
            "REGIONID": region,
            "INTERVENTION": intervention,
            "RRP": prices,
            "DATETIME": targets,
            "LASTCHANGED": published,
        }
    )


def raw_two_runs() -> pd.DataFrame:
    """Two runs, 30 minutes apart, that both forecast the half hour ending 05:30."""
    first = raw_run(
        "2026080101",
        "2026/08/01 04:01:23",
        ["2026/08/01 04:30:00", "2026/08/01 05:00:00", "2026/08/01 05:30:00"],
        ["75.4", "80.5", "-12.0"],
    )
    second = raw_run(
        "2026080102",
        "2026/08/01 04:31:20",
        ["2026/08/01 05:00:00", "2026/08/01 05:30:00"],
        ["81.0", "-15.5"],
    )
    return pd.concat([first, second], ignore_index=True)


def good_frame() -> pd.DataFrame:
    return tidy_predispatch(raw_two_runs(), "VIC1")


def test_tidy_predispatch_renames_and_converts_types() -> None:
    frame = good_frame()
    assert list(frame.columns) == PREDISPATCH_COLUMNS
    assert len(frame) == 5
    assert frame["forecast_price"].tolist() == [75.4, 80.5, -12.0, 81.0, -15.5]
    assert frame.loc[0, "published_at"] == pd.Timestamp("2026-08-01 04:01:23")
    assert frame.loc[0, "target_time"] == pd.Timestamp("2026-08-01 04:30:00")


def test_tidy_predispatch_keeps_every_run_for_the_same_target_time() -> None:
    frame = good_frame()
    same_target = frame[frame["target_time"] == pd.Timestamp("2026-08-01 05:30:00")]
    assert same_target["run_id"].tolist() == ["2026080101", "2026080102"]


def test_tidy_predispatch_drops_other_regions_and_intervention_runs() -> None:
    other_region = raw_run(
        "2026080101", "2026/08/01 04:01:23", ["2026/08/01 04:30:00"], ["1.0"], region="NSW1"
    )
    intervention = raw_run(
        "2026080101", "2026/08/01 04:01:23", ["2026/08/01 04:30:00"], ["2.0"], intervention="1"
    )
    raw = pd.concat([raw_two_runs(), other_region, intervention], ignore_index=True)
    assert len(tidy_predispatch(raw, "VIC1")) == 5


def test_good_data_has_no_problems() -> None:
    assert find_problems(good_frame()) == []
    validate_predispatch(good_frame())


def test_empty_table_is_reported() -> None:
    assert find_problems(good_frame().iloc[0:0]) == ["the table has no rows"]


def test_duplicate_row_is_reported() -> None:
    frame = pd.concat([good_frame(), good_frame().iloc[[0]]], ignore_index=True)
    assert "1 duplicate rows for the same run and target_time" in find_problems(frame)


def test_gap_inside_a_run_is_reported() -> None:
    frame = good_frame().drop(index=1).reset_index(drop=True)
    assert find_problems(frame) == ["1 gaps between target_time values inside a run"]


def test_forecast_published_after_its_target_time_is_reported() -> None:
    frame = good_frame()
    frame.loc[0, "target_time"] = pd.Timestamp("2026-08-01 04:00:00")
    problems = find_problems(frame)
    assert "1 rows where published_at is not before target_time" in problems


def test_run_with_two_publish_times_is_reported() -> None:
    frame = good_frame()
    frame.loc[1, "published_at"] = pd.Timestamp("2026-08-01 04:02:00")
    assert "1 runs with more than one published_at" in find_problems(frame)


def test_validate_raises_with_every_problem_listed() -> None:
    frame = good_frame()
    frame.loc[0, "forecast_price"] = None
    frame.loc[4, "forecast_price"] = -2000.0
    with pytest.raises(DataQualityError) as error:
        validate_predispatch(frame)
    message = str(error.value)
    assert "empty values in forecast_price" in message
    assert "below the market floor" in message
