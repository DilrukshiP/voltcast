"""Tests for the walk-forward backtest. They use a small made-up table."""

from datetime import date

import numpy as np
import pandas as pd

from voltcast.evals.backtest import (
    BAND_COLUMNS,
    PREDICTION_COLUMNS,
    Fold,
    monthly_folds,
    run_backtest,
    score_predictions,
)
from voltcast.model.columns import FEATURE_COLUMNS, TARGET_COLUMN
from voltcast.model.train import TrainingConfig

SMALL_CONFIG = TrainingConfig(
    num_leaves=7, min_data_in_leaf=10, max_rounds=40, early_stopping_rounds=10, tuning_days=5
)


def made_up_table() -> pd.DataFrame:
    """January to April 2025, hourly issue times with 4 targets each."""
    random = np.random.default_rng(11)
    rows = [
        {
            "issue_time": issue_time,
            "target_time": issue_time + step * pd.Timedelta(minutes=30),
            "step": step,
        }
        for issue_time in pd.date_range("2025-01-01", "2025-04-30 23:00", freq="h")
        for step in range(1, 5)
    ]
    table = pd.DataFrame(rows)
    for column in FEATURE_COLUMNS:
        table[column] = random.normal(0.0, 1.0, len(table))
    table["horizon_steps"] = table.pop("step")
    table[TARGET_COLUMN] = 60.0 + 20.0 * table["price_last"] + random.normal(0.0, 1.0, len(table))
    table["price_1d_ago"] = table[TARGET_COLUMN] + random.normal(0.0, 30.0, len(table))
    table["aemo_forecast_price"] = table[TARGET_COLUMN] + random.normal(0.0, 10.0, len(table))
    return table


def test_monthly_folds_cover_full_months_up_to_the_end() -> None:
    folds = monthly_folds(date(2025, 11, 1), date(2026, 2, 1))
    assert [fold.label for fold in folds] == ["2025-11", "2025-12", "2026-01"]
    assert folds[0] == Fold(pd.Timestamp("2025-11-01"), pd.Timestamp("2025-12-01"))
    assert folds[-1].end == pd.Timestamp("2026-02-01")


def test_monthly_folds_leave_out_a_month_that_is_cut_by_the_end() -> None:
    folds = monthly_folds(date(2025, 11, 1), date(2026, 1, 15))
    assert [fold.label for fold in folds] == ["2025-11", "2025-12"]


def test_backtest_forecasts_every_test_month_once() -> None:
    table = made_up_table()
    folds = monthly_folds(date(2025, 3, 1), date(2025, 5, 1))

    predictions = run_backtest(table, folds, SMALL_CONFIG)

    assert list(predictions.columns) == PREDICTION_COLUMNS
    assert sorted(predictions["test_month"].unique()) == ["2025-03", "2025-04"]
    assert not predictions.duplicated(subset=["issue_time", "target_time"]).any()
    assert predictions["model_forecast_price"].notna().all()


def test_each_forecast_lies_inside_its_own_test_month() -> None:
    table = made_up_table()
    predictions = run_backtest(
        table, monthly_folds(date(2025, 3, 1), date(2025, 5, 1)), SMALL_CONFIG
    )

    for month, part in predictions.groupby("test_month"):
        start = pd.Timestamp(f"{month}-01")
        end = start + pd.offsets.MonthBegin(1)
        assert part["issue_time"].min() >= start
        assert part["target_time"].max() <= end


def test_model_for_a_month_never_saw_that_month() -> None:
    """Change the prices of the last test month. Forecasts for earlier months must not move."""
    table = made_up_table()
    folds = monthly_folds(date(2025, 3, 1), date(2025, 5, 1))
    changed = table.copy()
    in_april = changed["target_time"] > pd.Timestamp("2025-04-01")
    changed.loc[in_april, TARGET_COLUMN] += 500.0

    before = run_backtest(table, folds, SMALL_CONFIG)
    after = run_backtest(changed, folds, SMALL_CONFIG)

    march = before["test_month"] == "2025-03"
    pd.testing.assert_series_equal(
        before.loc[march, "model_forecast_price"], after.loc[march, "model_forecast_price"]
    )
    april = before["test_month"] == "2025-04"
    assert (before.loc[april, TARGET_COLUMN] != after.loc[april, TARGET_COLUMN]).all()


def test_scores_compare_the_three_forecasts() -> None:
    predictions = run_backtest(
        made_up_table(), monthly_folds(date(2025, 4, 1), date(2025, 5, 1)), SMALL_CONFIG
    )
    everything = score_predictions(predictions).set_index("horizon").loc["0.5 to 4 hours"]
    assert everything["model_mae"] < everything["aemo_mae"] < everything["naive_mae"]


def test_band_is_added_and_never_crosses_the_median() -> None:
    table = made_up_table()
    folds = monthly_folds(date(2025, 4, 1), date(2025, 5, 1))

    with_band = run_backtest(table, folds, SMALL_CONFIG, with_band=True)

    assert list(with_band.columns) == [*PREDICTION_COLUMNS, *BAND_COLUMNS]
    assert (with_band["model_low_price"] <= with_band["model_forecast_price"]).all()
    assert (with_band["model_forecast_price"] <= with_band["model_high_price"]).all()
    assert (with_band["model_high_price"] > with_band["model_low_price"]).mean() > 0.95


def test_adding_the_band_does_not_change_the_median_forecast() -> None:
    table = made_up_table()
    folds = monthly_folds(date(2025, 4, 1), date(2025, 5, 1))

    without_band = run_backtest(table, folds, SMALL_CONFIG)
    with_band = run_backtest(table, folds, SMALL_CONFIG, with_band=True)

    pd.testing.assert_frame_equal(without_band, with_band[PREDICTION_COLUMNS])
