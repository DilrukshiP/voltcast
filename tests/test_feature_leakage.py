"""Leakage test: the future must not be able to change any model input.

The test builds the real dbt project twice on a small set of made-up raw files.
Between the two builds it changes every raw value that only became known after
one chosen moment, the cutoff. For every forecast issued at or before the cutoff,
all model inputs must be identical in both builds.

The test does not need to know how a leak could happen. It only observes
whether data from the future can reach an input.
"""

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from voltcast.model.columns import FEATURE_COLUMNS, KEY_COLUMNS, TARGET_COLUMN

DBT_PROJECT_DIR = Path(__file__).resolve().parents[1] / "dbt"
DBT_COMMAND = Path(sys.executable).parent / "dbt"

DATA_START = pd.Timestamp("2024-01-20 00:00")
DATA_END = pd.Timestamp("2024-02-12 00:00")
HISTORY_START = "2024-02-01"
CUTOFF = pd.Timestamp("2024-02-05 10:00")
AEMO_STEPS_PER_RUN = 40  # 20 hours, so the last steps of each forecast have no AEMO value


def make_actuals() -> pd.DataFrame:
    random = np.random.default_rng(1)
    times = pd.date_range(DATA_START + pd.Timedelta(minutes=5), DATA_END, freq="5min")
    return pd.DataFrame(
        {
            "region": "VIC1",
            "interval_end": times,
            "price": random.normal(60.0, 40.0, len(times)),
            "demand": random.uniform(3000.0, 8000.0, len(times)),
        }
    )


def make_predispatch() -> pd.DataFrame:
    random = np.random.default_rng(2)
    runs = []
    for run_start in pd.date_range(DATA_START, DATA_END, freq="30min"):
        targets = pd.date_range(
            run_start + pd.Timedelta(minutes=30), periods=AEMO_STEPS_PER_RUN, freq="30min"
        )
        runs.append(
            pd.DataFrame(
                {
                    "region": "VIC1",
                    "run_id": run_start.strftime("%Y%m%d%H%M"),
                    "published_at": run_start + pd.Timedelta(seconds=90),
                    "target_time": targets,
                    "forecast_price": random.normal(60.0, 40.0, len(targets)),
                }
            )
        )
    return pd.concat(runs, ignore_index=True)


def make_weather() -> pd.DataFrame:
    random = np.random.default_rng(3)
    times = pd.date_range(DATA_START, DATA_END, freq="h")
    frame = pd.DataFrame({"target_time": times})
    for name in ("temperature", "wind_speed", "solar_radiation"):
        for lead_day in (1, 2):
            frame[f"{name}_day{lead_day}"] = random.uniform(0.0, 30.0, len(times))
    return frame


def change_the_future(
    actuals: pd.DataFrame, predispatch: pd.DataFrame, weather: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Change every raw value that was not yet known at the cutoff."""
    actuals = actuals.copy()
    after = actuals["interval_end"] > CUTOFF
    actuals.loc[after, "price"] += 1000.0
    actuals.loc[after, "demand"] += 1000.0

    predispatch = predispatch.copy()
    published_later = predispatch["published_at"] >= CUTOFF
    predispatch.loc[published_later, "forecast_price"] += 5000.0

    # A forecast issued at the cutoff may use the one-day weather version up to 12 hours
    # ahead and the two-day version up to 24 hours ahead. Everything beyond is changed.
    weather = weather.copy()
    beyond_day1 = weather["target_time"] > CUTOFF + pd.Timedelta(hours=12)
    beyond_day2 = weather["target_time"] > CUTOFF + pd.Timedelta(hours=24)
    for name in ("temperature", "wind_speed", "solar_radiation"):
        weather.loc[beyond_day1, f"{name}_day1"] += 100.0
        weather.loc[beyond_day2, f"{name}_day2"] += 100.0
    return actuals, predispatch, weather


def build_features(
    data_dir: Path, actuals: pd.DataFrame, predispatch: pd.DataFrame, weather: pd.DataFrame
) -> pd.DataFrame:
    """Write the raw files, run the real dbt project on them, and return the training table."""
    for name, frame in (("actuals", actuals), ("predispatch", predispatch), ("weather", weather)):
        folder = data_dir / "raw" / name
        folder.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(folder / "2024-01.parquet", index=False)

    environment = {
        **os.environ,
        "VOLTCAST_DATA_DIR": str(data_dir),
        "VOLTCAST_HISTORY_START": HISTORY_START,
    }
    common = [
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
        "--target-path",
        str(data_dir / "dbt_target"),
        "--log-path",
        str(data_dir / "dbt_logs"),
    ]
    for step in ("seed", "run"):
        result = subprocess.run(
            [str(DBT_COMMAND), step, *common], env=environment, capture_output=True, text=True
        )
        assert result.returncode == 0, f"dbt {step} failed:\n{result.stdout}\n{result.stderr}"

    with duckdb.connect(str(data_dir / "voltcast.duckdb"), read_only=True) as connection:
        return connection.execute("select * from features order by issue_time, target_time").df()


@pytest.fixture(scope="module")
def before_and_after(tmp_path_factory: pytest.TempPathFactory) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the training table from the original data and from the data with a changed future."""
    actuals, predispatch, weather = make_actuals(), make_predispatch(), make_weather()
    before = build_features(tmp_path_factory.mktemp("before"), actuals, predispatch, weather)
    changed = change_the_future(actuals, predispatch, weather)
    after = build_features(tmp_path_factory.mktemp("after"), *changed)
    return before, after


def test_training_table_has_exactly_the_listed_columns(
    before_and_after: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    before, _ = before_and_after
    assert sorted(before.columns) == sorted([*KEY_COLUMNS, TARGET_COLUMN, *FEATURE_COLUMNS])


def test_both_builds_contain_the_same_forecasts(
    before_and_after: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    before, after = before_and_after
    assert len(before) > 0
    pd.testing.assert_frame_equal(before[KEY_COLUMNS], after[KEY_COLUMNS])
    assert (before["issue_time"] <= CUTOFF).sum() >= 48 * 24


def test_inputs_issued_up_to_the_cutoff_do_not_change(
    before_and_after: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    before, after = before_and_after
    issued_before = before["issue_time"] <= CUTOFF
    pd.testing.assert_frame_equal(
        before.loc[issued_before, FEATURE_COLUMNS],
        after.loc[issued_before, FEATURE_COLUMNS],
    )


def test_the_change_really_reached_the_future(
    before_and_after: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Without this test, a change that did nothing would also pass the test above."""
    before, after = before_and_after
    at_cutoff = before["issue_time"] == CUTOFF
    assert at_cutoff.sum() == 48
    changed_answers = before.loc[at_cutoff, TARGET_COLUMN] != after.loc[at_cutoff, TARGET_COLUMN]
    assert changed_answers.all()

    issued_later = before["issue_time"] == CUTOFF + pd.Timedelta(hours=2)
    for column in ("price_last", "aemo_forecast_price", "temperature_c"):
        differs = before.loc[issued_later, column] != after.loc[issued_later, column]
        assert differs.any(), f"{column} did not react to the changed data"
